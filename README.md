# Paimon.moe to UIGF Converter

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Version](https://img.shields.io/badge/version-1.1.0-brightgreen)

## 変更履歴 / Change Log

| Date       | Description                                    |
| ---------- | ---------------------------------------------- |
| 2025/12/27 | v1.0.0 Initial Release. UIGF v4.1 準拠        |
| 2026/11/14 | v1.1.0 UIGF v4.2 準拠（v4.1 変換オプション維持） |

## 概要 / Description

Paimon.moe の祈願履歴データをローカルで安全に処理し、**UIGF v3 → 最新スキーマ（v4.x）形式**へ自動変換する Python スクリプトです。
主に、日本ユーザーを対象としています。

- オンライン依存しないローカル変換
- [Paimon.moe](https://paimon.moe/) ローカルデータ対応
- [Genshin Dictionary](https://genshin-dictionary.com/ja) を使った日本語名補完
- rank-override.json による手動上書き（永続的学習）
- missing-rank.json による差分レポート
- [UIGF](https://uigf.org/en/) 標準（v3 / v4.1 / v4.2）対応

---

## ✨ 機能紹介 / Features

### ✔ Paimon.moe → UIGF v3 → UIGF v4.x 自動変換

[既存 Web アプリ](https://anishkn.com.np/uigfConverter/)では古いスキーマ（v3）のままですが、本ツールはローカルで **最新スキーマ v4.2** まで自動生成します。

> [!NOTE]
> UIGF により Version Upgrader が提供されていますが、本ツールでは、最新スキーマに一発変換できます。

> [!WARNING]
> v4.1 への変換オプションも残しておりますが、星反応に対応していないため推奨されません。

### ✔ `rank-override.json` による手動補完の永続化

ユーザーが手で補完した **`rank_type` / 日本語名 / 英語名** を`rank-override.json` に保存して、次回以降の変換に自動反映します。

一部 UIGF 準拠のツールでは、 Paimon.moe データに無い `rank_type` が必須となっているケースがあります。  
これに対応するためにユーザー側で補完し、より確実なデータとしてローカルに保持します。

> [!NOTE]
> 現状、公開情報や各種ツールから取得する方法が見つかっていないため、手動補完としております。
> もし、有益な情報があれば`issue`よりご連絡いただけますと幸いです。

### ✔ `missing-rank.json` による「人間の残タスク」可視化

`rank_type` が決められなかった項目のみ自動抽出し、`missing-rank.json` として出力することで、スクリプト改善や `rank-override` の追加に役立ちます。

### ✔ Genshin Dictionary 連携

英語名・日本語名の補完に Genshin Dictionary を使用し、不足しがちな日本語名を自動取得します。

---

## 📦 開発言語 / Requirements

- Python 3.9+  
   依存ライブラリは `requirements.txt` を参照してください。

最小構成：

```txt
requests>=2.31.0
```

---

## 📁 ファイル構造 / Directory Structure

```bash
pmoe-uigf-converter/
├── pm2uigf-pipeline.py        # メインスクリプト
├── rank-mapping-tool.py       # rank-override の作成やマージ
├── rank-override.json         # 手動補完データ（任意・自動読み込み）
|                              # マッピングツールの初回実行で出力
├── validate-uigf-v42.py       # UIGF v4.2 スキーマチェックスクリプト
├── validate-uigf-v41.py       # UIGF v4.1 スキーマチェックスクリプト（旧規格用）
├── UIGF-Schema/
|   ├── UIGF_v4.2_schema.json  # UIGF v4.2 スキーマ
|   └── UIGF_v4.1_schema.json  # UIGF v4.1 スキーマ
├── requirements.txt
├── README.md
├── .gitignore
└── LICENSE
```

---

## 🚀 利用方法 / Usage

### 1. 事前準備

```bash
pip install -r requirements.txt
```

あるいは

```bash
python -m pip install -r requirements.txt
```

### 2. 変換の実行（最も基本的な使い方）

既定では最新の **UIGF v4.2** 形式で出力されます。

```bash
python pm2uigf-pipeline.py uigf_v42.json \
    --paimon paimon-moe-local-data.json \
    --missing-rank-out missing-rank.json
```

※ 旧仕様の v4.1 形式で出力したい場合は `--target-version v4.1` を指定します（非推奨の確認警告メッセージが表示されます）。

```bash
python pm2uigf-pipeline.py uigf_v41.json \
    --paimon paimon-moe-local-data.json \
    --missing-rank-out missing-rank.json \
    --target-version v4.1
```

---

## 実行時オプション / Arguments

| オプション / Args                   | 順番 / Number of Args | 必須 / Requirement | 説明 / Description                                                                           |
| ----------------------------------- | --------------------- | ------------------ | -------------------------------------------------------------------------------------------- |
| `None` (指定なし)                   | 1                     | True               | 出力 UIGF v4.x ファイルパス                                                                  |
| `--paimon` <br> or <br> `--from-v3` | 2                     | True               | Paimon.moe ローカルデータ JSON <br> もしくは <br> UIGF v3 JSON                               |
| `--v3-out`                          | 3                     | False              | 途中生成した UIGF v3 JSON の出力先 <br> `--paimon` 指定時のみ指定可                          |
| `--missing-rank-out`                | 4                     | True (Conditional) | `rank_type` 未判別アイテム一覧の出力先 <br> `--paimon` 指定時のみ必須                        |
| `--export-app`                      | 5                     | False              | UIGF のプロパティに記載するエクスポートアプリの名前 <br> 既定値: `PMOE-Local-Converter`     |
| `--export-app-version`              | 6                     | False              | UIGF のプロパティに記載するエクスポートアプリのバージョン情報 <br> 既定値: `1.1.0`          |
| `--target-version`                  | 7                     | False              | 出力 UIGF バージョン <br> 既定値: `v4.2` <br> 選択肢: `v4.2`, `v4.1`                         |

## 📦 入力 / Input Files

| ファイル / File                                      | 説明 / Description                                     |
| ---------------------------------------------------- | ------------------------------------------------------ |
| `paimon-moe-local-data.json`<br>or<br>`uigf-v3.json` | Paimon.moe のローカル JSON<br>もしくは<br>UIGF v3 JSON |
| `rank-override.json`                                 | 人間が補完した rank/名前情報（自動適用）               |

> [!NOTE]
> Paimon.moe ローカルデータは `設定 → エクスポート/インポート → ダウンロード` にて取得できます。

## 📦 出力 / Output Files

| ファイル / File     | 説明 / Description                                     |
| ------------------- | ------------------------------------------------------ |
| `uigf_v42.json`     | UIGF v4.2（または v4.1）スキーマに準拠した最終 JSON     |
| `missing-rank.json` | `rank_type` が不明だった項目の一覧                    |

---

## 📄 `missing-rank.json` の例 / Example `missing-rank.json`

自動生成される「要手動補完リスト」です。

```json
{
  "generated_at": "2025-01-01T10:00:00",
  "items": [
    {
      "pmoe_id": "the_stringless",
      "name_en": "The Stringless",
      "name_jp": "",
      "gacha_type": "301"
    }
  ]
}
```

---

## 🧠 `rank-override.json` の使い方 / Usage for `rank-override.json`

手で書くべきファイル。
内容は自動で上書き・参照されます。

例:

```json
{
  "items": [
    {
      "pmoe_id": "magic_guide",
      "name_en": "Magic Guide",
      "name_jp": "魔導緒論",
      "rank_type": "3"
    },
    {
      "pmoe_id": "rust",
      "name_en": "Rust",
      "name_jp": "弓蔵",
      "rank_type": "4"
    }
  ]
}
```

### 🔰 初回（まだ `rank-override.json` が無い）

1. 初期 `rank-override.json` を作成：

   ```bash
   python rank-mapping-tool.py init missing-rank.json rank-override.json
   ```

2. 生成された `rank-override.json` をエディタで開き、`name_jp` や `rank_type` に自分でランクを記入

### 2回目以降（足りない分だけ追加）

1. 新しい `missing-rank.json` を生成（メインツールの新しい実行結果）
2. 「まだ `override` に無い分だけ」の一時ファイルを作成：

   ```bash
   python rank-mapping-tool.py todo missing-rank.json rank-override.json rank-todo.json
   ```

3. `rank-todo.json` を開いて、`name_jp` や `rank_type` を埋める
   （空のものは無視されるので、分からないものは空のままで）
4. `rank-override.json` にマージ：

   ```bash
   python rank-mapping-tool.py merge rank-override.json rank-todo.json
   ```

---

## 🛠 Development

フォーマット

```bash
black pm2uigf-pipeline.py
```

スキーマ検証を行う場合

```bash
pip install jsonschema

# v4.2 の検証
python validate-uigf-v42.py UIGF-Schema/UIGF_v4.2_schema.json uigf_v42.json

# v4.1 の検証
python validate-uigf-v41.py UIGF-Schema/UIGF_v4.1_schema.json uigf_v41.json
```

---

### 📜 License

MIT License

---

## 免責事項

完全個人開発ゆえ、以下各所への問い合わせはご遠慮ください。

### 🌐 Data Sources

- [Paimon.moe](https://paimon.moe/)
- [UIGF（Universal Interchangeable Gacha Format）](https://uigf.org/)
- [Genshin Dictionary](https://genshin-dictionary.com/)

---

## 🙏 Acknowledgements

- Paimon.moe
- UIGF 開発チーム
- Genshin Dictionary

各データ提供者の皆さまに感謝します。
