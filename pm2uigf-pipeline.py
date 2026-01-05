#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Paimon.moe ローカルデータ → UIGF v3 → UIGF v4.1 変換パイプライン
"""

import argparse
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

# ディレクトリ・ファイルパス定義
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RANK_OVERRIDE_FILE = os.path.join(SCRIPT_DIR, "rank-override.json")

# API URL 定義
API_URLS = {
    "weapons_en": "https://raw.githubusercontent.com/MadeBaruna/paimon-moe/main/src/data/weapons/en.json",
    "weapons_ja": "https://raw.githubusercontent.com/MadeBaruna/paimon-moe/main/src/data/weapons/ja.json",
    "characters_en": "https://raw.githubusercontent.com/MadeBaruna/paimon-moe/main/src/data/furnishing/en.json",
    "characters_ja": "https://raw.githubusercontent.com/MadeBaruna/paimon-moe/main/src/data/furnishing/ja.json",
    "uigf_dict_en": "https://api.uigf.org/dict/genshin/en.json",
    "uigf_dict_ja": "https://api.uigf.org/dict/genshin/jp.json",
    "genshin_words": "https://dataset.genshin-dictionary.com/words.json",
}

# まずは英語と日本語に限定
LANG_MAP = {
    "ja": "ja-jp", "en": "en-us",
#    "de": "de-de", "es": "es-es",
#    "fr": "fr-fr", "id": "id-id", "it": "it-it", "ko": "ko-kr",
#    "pt": "pt-pt", "ru": "ru-ru", "th": "th-th", "tr": "tr-tr",
#    "vi": "vi-vn", "zh-cn": "zh-cn", "zh-tw": "zh-tw",
}

GACHA_BANNER_TYPES = [
    ("wish-counter-beginners", 100),
    ("wish-counter-character-event", 301),
    ("wish-counter-weapon-event", 302),
    ("wish-counter-standard", 200),
    ("wish-counter-chronicled", 500),
]

# ===== ユーティリティ =====

def normalize_en_key(s: str) -> str:
    """英語名を正規化（比較用）"""
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.replace("_", " ")).strip().lower()

def english_from_pmoe_id(pmoe_id: str) -> str:
    """pmoe_id から英語名を推測"""
    norm = normalize_en_key(pmoe_id)
    return " ".join(w.capitalize() for w in norm.split()) if norm else ""

def parse_time(time_str: str) -> Optional[datetime]:
    """時刻文字列をパース"""
    try:
        return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None

# ===== API取得（並列化） =====

def fetch_json(url: str, timeout: int = 10) -> dict:
    """JSON をURLから取得"""
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"警告: {url} の取得に失敗: {e}")
        return {}

def fetch_apis_parallel() -> Dict[str, Any]:
    """複数のAPI呼び出しを並列実行"""
    results = {}
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_json, url): key for key, url in API_URLS.items()}
        for future in as_completed(futures):
            key = futures[future]
            results[key] = future.result()
    return results

def build_pmoe_dict(api_results: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Paimon.moe 辞書を構築"""
    pmoe = {}
    for key in ("weapons_en", "weapons_ja", "characters_en", "characters_ja"):
        lang = "en" if "en" in key else "jp"
        data = api_results.get(key, {})
        for pmoe_id, info in data.items():
            if not isinstance(info, dict):
                continue
            entry = pmoe.setdefault(pmoe_id, {})
            if "name" in info and f"name_{lang}" not in entry:
                entry[f"name_{lang}"] = info["name"]
            if "rarity" in info and "rarity" not in entry:
                entry["rarity"] = info["rarity"]
    return pmoe

def build_genshin_words_maps(gd_data: dict) -> Dict[str, Dict[str, str]]:
    """Genshin Dictionary マップを構築"""
    maps = {"en_to_ja": {}, "en_to_ja_norm": {}, "zh_to_ja": {}}
    if not isinstance(gd_data, list):
        return maps
    
    for w in gd_data:
        if not isinstance(w, dict) or "ja" not in w:
            continue
        ja = w["ja"]
        
        if "en" in w:
            maps["en_to_ja"][w["en"]] = ja
            norm_key = normalize_en_key(w["en"])
            if norm_key:
                maps["en_to_ja_norm"][norm_key] = ja
        
        if "zhCN" in w:
            maps["zh_to_ja"][w["zhCN"]] = ja
    
    return maps

# ===== ランク・アイテム情報 =====

def get_item_names_from_pmoe_id(pmoe_id: str, pmoe_dict: dict) -> Tuple[str, str]:
    """pmoe_id から英語名・日本語名を取得"""
    data = pmoe_dict.get(pmoe_id, {})
    return data.get("name_en") or data.get("name", ""), data.get("name_jp", "")

def get_rank_from_pmoe_id(pmoe_id: str, pmoe_dict: dict) -> Optional[str]:
    """pmoe_id から rarity を取得"""
    data = pmoe_dict.get(pmoe_id, {})
    r = data.get("rarity")
    return str(r) if isinstance(r, (int, str)) else None

def get_item_id_from_name(name: str, uigf_dict: dict) -> str:
    """名前から item_id を取得"""
    return str(uigf_dict.get(name, 0))

def resolve_item_name(
    pmoe_id: str, raw_name: str, pmoe_dict: dict, 
    gd_maps: Dict[str, Dict[str, str]], locale: str
) -> Tuple[str, str]:
    """アイテム名を複合的に解決"""
    item_name_en, item_name_jp = get_item_names_from_pmoe_id(pmoe_id, pmoe_dict)
    derived_en = english_from_pmoe_id(pmoe_id)
    
    en_to_ja = gd_maps.get("en_to_ja", {})
    en_to_ja_norm = gd_maps.get("en_to_ja_norm", {})
    zh_to_ja = gd_maps.get("zh_to_ja", {})
    
    # 英語名の確定
    if not item_name_en:
        item_name_en = derived_en or raw_name
    
    # 日本語名を推測
    if not item_name_jp:
        for en_text in (item_name_en, derived_en, raw_name):
            if en_text:
                item_name_jp = en_to_ja.get(en_text) or en_to_ja_norm.get(normalize_en_key(en_text))
                if item_name_jp:
                    break
        
        if not item_name_jp and raw_name:
            item_name_jp = zh_to_ja.get(raw_name)
    
    # 最後の手段：両方空なら raw_name を使う
    if not item_name_en and not item_name_jp:
        if (locale or "").lower().startswith("ja"):
            item_name_jp = raw_name
        else:
            item_name_en = raw_name
    
    return item_name_en, item_name_jp

def apply_rank_override(
    pmoe_id: str, item_name_en: str, item_name_jp: str, rank_type: Optional[str],
    override_map: Dict[str, Dict[str, Any]]
) -> Tuple[str, str, Optional[str]]:
    """rank-override を適用"""
    override = override_map.get(pmoe_id)
    if not override:
        return item_name_en, item_name_jp, rank_type
    
    if o_name := override.get("name_en"):
        item_name_en = str(o_name).strip()
    if o_name := override.get("name_jp"):
        item_name_jp = str(o_name).strip()
    if o_rank := override.get("rank_type"):
        rank_type = str(o_rank).strip()
    
    return item_name_en, item_name_jp, rank_type

# ===== Paimon → UIGF v3 =====

def infer_lang_from_locale(locale: str) -> str:
    """locale を lang に変換"""
    return LANG_MAP.get((locale or "en").lower(), "en-us")

def infer_timezone_from_uid(uid: str) -> int:
    """UID から タイムゾーン を推測"""
    if uid and len(uid) > 0:
        first = uid[0]
        if first == "6":
            return -5
        if first == "7":
            return 1
    return 8

def to_uigf_gacha_type(gacha_type: str) -> str:
    """gacha_type を UIGF形式に変換"""
    return "301" if gacha_type == "400" else gacha_type

def build_uigf_record(
    pull: dict, gacha_type: str, pmoe_id: str, item_name_en: str, 
    item_name_jp: str, item_id: str, rank_type: Optional[str], rec_id: str, lang: str = "en-us"
) -> Optional[dict]:
    """ガチャレコードを構築"""
    time_str = str(pull.get("time", ""))
    if not time_str or not parse_time(time_str):
        return None
    
    # 言語が ja-jp の場合は item_name_jp を優先
    display_name = item_name_jp if lang == "ja-jp" else (item_name_en or item_name_jp)
    
    entry = {
        "uigf_gacha_type": to_uigf_gacha_type(gacha_type),
        "gacha_type": gacha_type,
        "item_id": item_id,
        "time": time_str,
        "id": rec_id,
        "count": "1",
        "name": display_name or str(pull.get("name", "")),
    }
    
    p_type = str(pull.get("type", "")).lower()
    if p_type in ("weapon", "character"):
        # 日本語ロケールでは日本語表記を使う
        if str(lang).lower() == "ja-jp":
            entry["item_type"] = "武器" if p_type == "weapon" else "キャラクター"
        else:
            entry["item_type"] = p_type.capitalize()
    
    if rank_type:
        entry["rank_type"] = rank_type
    
    return entry

def paimon_to_uigf_v3(
    paimon_data: Dict[str, Any],
    export_app: str = "PMOE-Local-Converter",
    export_app_version: str = "1.0.2",
    rank_override_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, str]]]:
    """Paimon → UIGF v3"""
    if rank_override_map is None:
        rank_override_map = {}
    
    # API並列取得
    api_results = fetch_apis_parallel()
    pmoe_dict = build_pmoe_dict(api_results)
    uigf_dict = api_results.get("uigf_dict", {})
    gd_maps = build_genshin_words_maps(api_results.get("genshin_words", []))
    
    # 基本情報
    uid = str(paimon_data.get("wish-uid") or paimon_data.get("uid") or "0")
    locale = paimon_data.get("locale") or "en"
    lang = infer_lang_from_locale(locale)
    region_time_zone = infer_timezone_from_uid(uid)
    
    now = datetime.now()
    export_timestamp = int(now.timestamp())
    export_time = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # レコード構築
    uigf_list = []
    missing_rank: Dict[str, Dict[str, str]] = {}
    synth_id = int(f"{uid}000000") if uid.isdigit() else int(datetime.now().timestamp())
    
    for counter_key, gacha_type_int in GACHA_BANNER_TYPES:
        counter = paimon_data.get(counter_key)
        if not isinstance(counter, dict):
            continue
        
        pulls = counter.get("pulls") or []
        for p in pulls:
            pmoe_id = str(p.get("id", ""))
            raw_name = str(p.get("name", ""))
            gacha_type = str(gacha_type_int)
            
            item_name_en, item_name_jp = resolve_item_name(
                pmoe_id, raw_name, pmoe_dict, gd_maps, locale
            )
            
            item_id = get_item_id_from_name(item_name_en, uigf_dict)
            if item_id == "0" and raw_name:
                item_id = get_item_id_from_name(raw_name, uigf_dict)
            
            rank_type = get_rank_from_pmoe_id(pmoe_id, pmoe_dict)
            item_name_en, item_name_jp, rank_type = apply_rank_override(
                pmoe_id, item_name_en, item_name_jp, rank_type, rank_override_map
            )
            
            synth_id += 1
            rec_id = str(synth_id)
            
            entry = build_uigf_record(
                p, gacha_type, pmoe_id, item_name_en, item_name_jp,
                item_id, rank_type, rec_id, lang
            )
            
            if entry:
                uigf_list.append(entry)
            
            if not rank_type:
                missing_rank[pmoe_id] = {
                    "name_en": item_name_en,
                    "name_jp": item_name_jp,
                    "gacha_type": gacha_type,
                }
    
    uigf_list.sort(key=lambda e: (e["time"], e["id"]))
    
    uigf_v3 = {
        "info": {
            "uid": uid,
            "lang": lang,
            "export_timestamp": export_timestamp,
            "export_time": export_time,
            "export_app": export_app,
            "export_app_version": export_app_version,
            "uigf_version": "v3.0",
            "region_time_zone": region_time_zone,
        },
        "list": uigf_list,
    }
    
    return uigf_v3, missing_rank

# ===== UIGF v3 → v4.x =====

def uigf_v3_to_v41(uigf_v3: Dict[str, Any], version: str = "v4.1") -> Dict[str, Any]:
    """UIGF v3 → v4.1"""
    info_v3 = uigf_v3.get("info", {})
    list_v3 = uigf_v3.get("list", [])
    
    info_v41 = {
        "export_timestamp": info_v3.get("export_timestamp"),
        "export_app": info_v3.get("export_app"),
        "export_app_version": info_v3.get("export_app_version"),
        "version": version,
    }
    
    list_v41 = []
    for r in list_v3:
        gacha_type = str(r.get("gacha_type", ""))
        if not gacha_type or "time" not in r or "id" not in r:
            continue
        
        entry = {
            "uigf_gacha_type": to_uigf_gacha_type(str(r.get("uigf_gacha_type", gacha_type))),
            "gacha_type": gacha_type,
            "item_id": str(r.get("item_id", "")),
            "time": r["time"],
            "id": str(r["id"]),
            "count": str(r.get("count", "1")),
        }
        
        for k in ("name", "item_type", "rank_type"):
            if k in r and r[k] is not None:
                entry[k] = str(r[k])
        
        list_v41.append(entry)
    
    list_v41.sort(key=lambda e: (e["time"], e["id"]))
    
    return {
        "info": info_v41,
        "hk4e": [
            {
                "uid": info_v3.get("uid", "0"),
                "timezone": info_v3.get("region_time_zone", 8),
                "lang": info_v3.get("lang", "en-us"),
                "list": list_v41,
            }
        ],
    }

def uigf_v3_to_v4x(uigf_v3: Dict[str, Any], target_version: str = "v4.1") -> Dict[str, Any]:
    """将来の拡張を想定した v3→v4.x 入口"""
    if target_version.startswith("v4.1"):
        return uigf_v3_to_v41(uigf_v3, version=target_version)
    raise ValueError(f"未対応の UIGF バージョンです: {target_version}")

# ===== CLI & ファイルI/O =====

def load_rank_override() -> Dict[str, Dict[str, Any]]:
    """rank-override.json を読み込む"""
    rank_override_map = {}
    if not os.path.exists(RANK_OVERRIDE_FILE):
        return rank_override_map
    
    try:
        with open(RANK_OVERRIDE_FILE, "r", encoding="utf-8") as f:
            override_obj = json.load(f)
        for item in override_obj.get("items", []):
            if pmoe_id := item.get("pmoe_id"):
                rank_override_map[pmoe_id] = item
        print(f"rank-override を {len(rank_override_map)} 件読み込みました")
    except (json.JSONDecodeError, OSError) as e:
        print(f"警告: rank-override.json の読み込みに失敗: {e}")
    
    return rank_override_map

def load_json_file(path: str) -> dict:
    """JSONファイルを読み込む"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"ファイルが見つかりません: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"JSON のパースに失敗しました: {path} - {e}")

def save_json_file(path: str, data: dict, description: str = ""):
    """JSONファイルを保存"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        msg = f"{description} を出力しました: {path}"
        print(msg)
    except OSError as e:
        print(f"警告: ファイルの書き込みに失敗しました: {path} - {e}")

def output_missing_rank(missing_rank: Dict[str, Dict[str, str]], output_path: str):
    """rank_type 不明アイテムを出力"""
    if not missing_rank or not output_path:
        return
    
    out_obj = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "items": [
            {
                "pmoe_id": pmoe_id,
                "name_en": info.get("name_en"),
                "name_jp": info.get("name_jp"),
                "gacha_type": info.get("gacha_type"),
            }
            for pmoe_id, info in missing_rank.items()
        ],
    }
    save_json_file(output_path, out_obj, "rank_type 未判別アイテム一覧")

def main():
    parser = argparse.ArgumentParser(
        description="Paimon.moe ローカルデータ → UIGF v3 → UIGF v4.1 変換"
    )
    
    parser.add_argument("output_v41", help="出力 UIGF v4.x ファイルパス")
    parser.add_argument("--paimon", help="Paimon.moe ローカルデータ JSON")
    parser.add_argument("--from-v3", help="既存の UIGF v3 JSON")
    parser.add_argument("--v3-out", help="生成した UIGF v3 JSON の出力先")
    parser.add_argument("--missing-rank-out", help="rank_type 未判別アイテム一覧の出力先")
    parser.add_argument("--export-app", default="PMOE-Local-Converter")
    parser.add_argument("--export-app-version", default="1.0.0")
    parser.add_argument("--target-version", default="v4.1")
    
    args = parser.parse_args()
    
    # モード判定
    if not args.paimon and not args.from_v3:
        raise SystemExit("エラー: --paimon か --from-v3 のどちらか一方を指定してください")
    if args.paimon and args.from_v3:
        raise SystemExit("エラー: --paimon と --from-v3 は同時には指定できません")
    
    # rank-override を読み込む
    rank_override_map = load_rank_override()
    
    uigf_v3 = None
    
    # Paimon → v3
    if args.paimon:
        paimon_data = load_json_file(args.paimon)
        uigf_v3, missing_rank = paimon_to_uigf_v3(
            paimon_data,
            export_app=args.export_app,
            export_app_version=args.export_app_version,
            rank_override_map=rank_override_map,
        )
        
        if args.v3_out:
            save_json_file(args.v3_out, uigf_v3, "UIGF v3 JSON")
        
        output_missing_rank(missing_rank, args.missing_rank_out)
    
    # 既存 v3 を読み込む
    if args.from_v3:
        uigf_v3 = load_json_file(args.from_v3)
    
    # v3 → v4.x
    v4x = uigf_v3_to_v4x(uigf_v3, target_version=args.target_version)
    save_json_file(args.output_v41, v4x, f"UIGF {args.target_version} JSON")

if __name__ == "__main__":
    main()
