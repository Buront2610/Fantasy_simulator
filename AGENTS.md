# AGENTS.md

## Project Overview

Fantasy Simulator: Python CLI世界シミュレーション（Aethoria）。純粋Python 3.10+、外部依存なし。

## Architecture

- **エントリーポイント**: `main.py` → CLIメニューループ
- **シミュレーション**: `simulator.py` が年次ループを管理、`events.py` がイベント生成、`adventure.py` が冒険進行
- **データモデル**: `character.py`（キャラ）、`world.py`（ワールド・マップ）、`world_data.py`（ゲーム定義）
- **UI**: `screens.py`（画面制御）、`ui_helpers.py`（表示ユーティリティ）
- **永続化**: `save_load.py`（JSON）、`i18n.py`（多言語）

## Directory Structure

```
Fantasy_simulator/
├── main.py                  # CLIエントリーポイント
├── character.py             # Character クラス
├── character_creator.py     # キャラクター生成
├── world.py                 # World クラス、Location
├── world_data.py            # 種族、職業、スキル定義
├── simulator.py             # Simulator クラス（年次ループ）
├── events.py                # EventSystem クラス
├── adventure.py             # Adventure クラス
├── screens.py               # UI画面
├── ui_helpers.py            # 表示ヘルパー
├── save_load.py             # セーブ/ロード
├── i18n.py                  # 翻訳システム
├── tests/
│   ├── conftest.py          # テストfixture
│   └── test_*.py            # 各モジュールのテスト
├── .github/workflows/
│   └── test.yml             # CI設定
├── CLAUDE.md                # Claude Code設定
└── README.md                # プロジェクト説明
```

## Coding Conventions

- snake_case（変数・関数）、PascalCase（クラス）
- 行の最大長: 120文字
- ユーザー向け文字列は `t()` 経由（i18n）
- シリアライズは `to_dict()` / `from_dict()` パターン
- テストは `tests/test_<module>.py`

## Setup & Validation

```bash
# 実行
python main.py

# テスト
python -m pytest tests/ -v

# Lint
flake8 --max-line-length=120 --exclude=node_modules,__pycache__ .

# 一括検証
flake8 --max-line-length=120 --exclude=node_modules,__pycache__ . && python -m pytest tests/ -v
```

## NEVER

- 外部パッケージの依存を追加しない（純粋Python標準ライブラリのみ）
- `node_modules/`、`__pycache__/` を編集しない
- 既存のテストを削除しない
- `i18n.py` の翻訳キー構造を壊さない
- flake8 エラーを残さない
- ハードコードされたユーザー向け文字列を追加しない（`t()` を使う）
- `save_load.py` のシリアライゼーション互換性を壊さない

## Permissions

### 自由に変更可能
- `tests/` 配下のテストファイル
- `i18n.py` への翻訳文字列の追加
- 既存モジュール内のバグ修正・リファクタリング

### レビュー推奨
- `world_data.py` のゲームバランスに関わる値
- `character.py` のシリアライゼーション構造
- `simulator.py` のシミュレーションループ変更

### 変更禁止（確認必須）
- `.github/workflows/` CI設定
- `save_load.py` の保存フォーマット（後方互換性）
- `main.py` のメニュー構造の大幅変更

## Code Examples

### キャラクター作成
```python
from character import Character
char = Character(
    name="Aldric", race="Human", job="Warrior",
    stats={"strength": 15, "intelligence": 8, "dexterity": 12,
           "wisdom": 10, "charisma": 11, "constitution": 14}
)
```

### イベント生成
```python
from events import EventSystem
es = EventSystem(world, seed=42)
events = es.generate_events(year=5, events_per_year=3)
for event in events:
    es.resolve_event(event)
```

### 翻訳文字列の追加
```python
# i18n.py の TRANSLATIONS 辞書に追加
"events.new_event": {
    "en": "A new event occurred: {description}",
    "ja": "新しいイベントが発生しました: {description}"
}
# 使用時
from i18n import t
message = t("events.new_event").format(description="...")
```
