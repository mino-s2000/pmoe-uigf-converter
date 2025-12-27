#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
rank_mapping_tool.py

Paimon.moe → UIGF 変換で足りない rank_type を管理するための補助ツール。

サブコマンド:
  - init  : missing-rank.json から rank-override.json を初期生成
  - todo  : 新しい missing-rank.json から未登録項目だけを追記用ファイルとして出力
  - merge : 追記用ファイルに書いた rank_type を rank-override.json に取り込む
"""

import argparse
import json
from typing import Any, Dict, List, Set


# ===== ファイルI/O =====

def load_json(path: str) -> Any:
    """JSON ファイルを読み込む"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"ファイルが見つかりません: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"JSON のパースに失敗しました: {path} - {e}")


def save_json(path: str, obj: Any) -> None:
    """JSON ファイルを保存"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except OSError as e:
        raise SystemExit(f"ファイル保存に失敗しました: {path} - {e}")


# ===== 共通ユーティリティ =====

def extract_items_from_missing(missing_data: dict) -> List[Dict[str, Any]]:
    """missing-rank.json から items リストを抽出（重複排除済み）"""
    items = missing_data.get("items", [])
    seen: Set[str] = set()
    unique_items: List[Dict[str, Any]] = []
    
    for item in items:
        pmoe_id = item.get("pmoe_id")
        if pmoe_id and pmoe_id not in seen:
            seen.add(pmoe_id)
            unique_items.append(item)
    
    return unique_items


def get_existing_pmoe_ids(override_data: dict) -> Set[str]:
    """rank-override.json に既に登録されている pmoe_id を取得"""
    items = override_data.get("items", [])
    return {it.get("pmoe_id") for it in items if it.get("pmoe_id")}


def build_override_entry(item: dict) -> dict:
    """missing アイテムから rank-override エントリを構築"""
    return {
        "pmoe_id": item.get("pmoe_id"),
        "name_en": item.get("name_en"),
        "name_jp": item.get("name_jp"),
        "gacha_type": item.get("gacha_type"),
        "rank_type": "",  # ユーザーが手で埋める
    }


def merge_override_entry(new_item: dict, existing_entry: dict) -> dict:
    """新しいアイテムを既存エントリにマージ"""
    pmoe_id = new_item.get("pmoe_id")
    rank_type = new_item.get("rank_type")
    
    if rank_type is None or str(rank_type).strip() == "":
        return existing_entry
    
    return {
        "pmoe_id": pmoe_id,
        "name_en": new_item.get("name_en", existing_entry.get("name_en")),
        "name_jp": new_item.get("name_jp", existing_entry.get("name_jp")),
        "gacha_type": new_item.get("gacha_type", existing_entry.get("gacha_type")),
        "rank_type": str(rank_type),
    }


# ===== サブコマンド実装 =====

def cmd_init(args: argparse.Namespace) -> None:
    """missing-rank.json から rank-override.json を初期生成"""
    print(f"読み込み: {args.missing}")
    missing_data = load_json(args.missing)
    
    items = extract_items_from_missing(missing_data)
    out_items = [build_override_entry(item) for item in items]
    
    override = {
        "version": "1.0",
        "items": out_items,
    }
    
    save_json(args.override, override)
    print(f"✓ rank-override.json を生成しました: {args.override}")
    print(f"  {len(out_items)} 件のエントリを作成しました")
    print("→ rank_type 列に手動でランクを記入してください\n")


def cmd_todo(args: argparse.Namespace) -> None:
    """新しい missing-rank.json から未登録項目を追記用ファイルとして出力"""
    print(f"読み込み: {args.missing}")
    missing_data = load_json(args.missing)
    print(f"読み込み: {args.override}")
    override_data = load_json(args.override)
    
    missing_items = extract_items_from_missing(missing_data)
    existing_ids = get_existing_pmoe_ids(override_data)
    
    # 未登録の項目だけを抽出
    new_items = [
        build_override_entry(item)
        for item in missing_items
        if item.get("pmoe_id") not in existing_ids
    ]
    
    out_obj = {
        "base_missing_file": args.missing,
        "items": new_items,
    }
    
    save_json(args.out, out_obj)
    print(f"✓ 追記用一時ファイルを出力しました: {args.out}")
    print(f"  {len(new_items)} 件の新規アイテムが見つかりました")
    print("→ rank_type 列にランクを記入し、merge コマンドで取り込んでください\n")


def cmd_merge(args: argparse.Namespace) -> None:
    """追記用ファイルを rank-override.json に反映"""
    print(f"読み込み: {args.override}")
    override_data = load_json(args.override)
    print(f"読み込み: {args.todo}")
    todo_data = load_json(args.todo)
    
    # 既存の rank-override を辞書化（pmoe_id をキー）
    override_items = override_data.get("items", [])
    override_map: Dict[str, dict] = {
        it.get("pmoe_id"): dict(it)
        for it in override_items
        if it.get("pmoe_id")
    }
    
    # todo ファイルの各項目をマージ
    todo_items = todo_data.get("items", [])
    updated_count = 0
    added_count = 0
    
    for todo_item in todo_items:
        pmoe_id = todo_item.get("pmoe_id")
        if not pmoe_id:
            continue
        
        existing = override_map.get(pmoe_id, {})
        merged = merge_override_entry(todo_item, existing)
        
        # rank_type が空なら反映しない（スキップ）
        if not merged.get("rank_type"):
            continue
        
        if pmoe_id in override_map:
            updated_count += 1
        else:
            added_count += 1
        
        override_map[pmoe_id] = merged
    
    # ソート済みで保存
    new_items = [
        override_map[pmoe_id]
        for pmoe_id in sorted(override_map.keys())
    ]
    override_data["items"] = new_items
    
    save_json(args.override, override_data)
    print(f"✓ rank-override.json を更新しました: {args.override}")
    print(f"  新規追加: {added_count} 件, 更新: {updated_count} 件\n")


# ===== CLI エントリポイント =====

def main():
    parser = argparse.ArgumentParser(
        description="rank_type 対応表 (rank-override.json) を管理するツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 初回: missing-rank.json から rank-override.json を生成
  python rank-mapping-tool.py init missing-rank.json rank-override.json

  # 新規: 新しい missing-rank.json から追記用ファイルを生成
  python rank-mapping-tool.py todo missing-rank.json rank-override.json rank-todo.json

  # マージ: 追記用ファイルを rank-override.json に取り込む
  python rank-mapping-tool.py merge rank-override.json rank-todo.json
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="実行するサブコマンド")

    # init
    p_init = subparsers.add_parser(
        "init",
        help="missing-rank.json から rank-override.json を初期生成"
    )
    p_init.add_argument("missing", help="missing-rank.json のパス")
    p_init.add_argument("override", help="生成する rank-override.json のパス")
    p_init.set_defaults(func=cmd_init)

    # todo
    p_todo = subparsers.add_parser(
        "todo",
        help="新しい missing-rank.json から未登録アイテムの追記用ファイルを生成"
    )
    p_todo.add_argument("missing", help="新しい missing-rank.json のパス")
    p_todo.add_argument("override", help="既存 rank-override.json のパス")
    p_todo.add_argument("out", help="追記用一時ファイルの出力パス (例: rank-todo.json)")
    p_todo.set_defaults(func=cmd_todo)

    # merge
    p_merge = subparsers.add_parser(
        "merge",
        help="追記用一時ファイルを rank-override.json に取り込む"
    )
    p_merge.add_argument("override", help="既存 rank-override.json のパス (上書き保存)")
    p_merge.add_argument("todo", help="追記用一時ファイル (rank-todo.json 等)")
    p_merge.set_defaults(func=cmd_merge)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
