#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
validate-uigf-v41.py

UIGF v4.1 JSON ファイルを公式スキーマで検証するツール。
"""

import argparse
import json
import sys
from typing import Any, Dict

try:
    from jsonschema import validate
    from jsonschema.exceptions import ValidationError
except ImportError:
    print("エラー: jsonschema ライブラリがインストールされていません")
    print("インストール: pip install jsonschema")
    sys.exit(1)


# ===== ファイルI/O =====

def load_json(path: str, description: str = "") -> dict:
    """JSON ファイルを読み込む"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"ファイルが見つかりません: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"JSON のパースに失敗しました: {path} - {e}")


# ===== スキーマ検証 =====

def validate_uigf(schema: Dict[str, Any], data: Dict[str, Any]) -> bool:
    """
    UIGF v4.1 JSON をスキーマで検証する
    
    戻り値:
      True: 検証成功
      False: 検証失敗（エラーメッセージは既に出力済み）
    """
    try:
        validate(instance=data, schema=schema)
        return True
    except ValidationError as e:
        path_str = "/".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
        print(f"✗ スキーマ検証エラー")
        print(f"  パス: {path_str}")
        print(f"  メッセージ: {e.message}")
        if e.validator:
            print(f"  検証ルール: {e.validator}")
        return False


# ===== CLI エントリポイント =====

def main():
    parser = argparse.ArgumentParser(
        description="UIGF v4.1 JSON をスキーマで検証するツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python validate-uigf-v41.py uigf-v4.1.schema.json uigf_v41.json
        """,
    )
    parser.add_argument("schema", help="UIGF v4.1 スキーマ JSON ファイル")
    parser.add_argument("data", help="検証したい UIGF v4.1 JSON ファイル")
    
    args = parser.parse_args()
    
    # スキーマ・データを読み込む
    print(f"スキーマ読み込み: {args.schema}")
    schema = load_json(args.schema)
    
    print(f"データ読み込み: {args.data}")
    data = load_json(args.data)
    
    # 検証実行
    print("\n検証中...\n")
    if validate_uigf(schema, data):
        print("✓ スキーマ v4.1 に準拠しています\n")
        return 0
    else:
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
