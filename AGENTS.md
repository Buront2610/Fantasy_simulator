# AGENTS.md

## Project Overview

Fantasy Simulator: Python CLI世界シミュレーション（Aethoria）。Python 3.10+。ランタイムは現時点で標準ライブラリのみだが、必要に応じて外部パッケージを導入してよい。

## Architecture

- **エントリーポイント**: `python -m fantasy_simulator` → `fantasy_simulator/main.py`（互換: `python main.py`）
- **シミュレーション**: `simulator.py` が年次ループを管理、`events.py` がイベント生成、`adventure.py` が冒険進行
- **データモデル**: `character.py`（キャラ）、`world.py`（ワールド・マップ）、`content/world_data.py`（ゲーム定義）
- **UI**: `ui/screens.py`（画面制御）、`ui/ui_helpers.py`（表示ユーティリティ）
- **永続化**: `persistence/save_load.py`（JSON）、`i18n/`（多言語）

## Directory Structure

```
Fantasy_simulator/
├── main.py                              # 互換ラッパー
├── fantasy_simulator/
│   ├── __init__.py
│   ├── __main__.py                      # python -m fantasy_simulator
│   ├── main.py                          # CLIメニューループ本体
│   ├── character.py                     # Character クラス
│   ├── character_creator.py             # キャラクター生成
│   ├── world.py                         # World クラス、LocationState
│   ├── simulator.py                     # Simulator クラス（年次ループ）
│   ├── events.py                        # EventSystem クラス
│   ├── adventure.py                     # Adventure クラス
│   ├── reports.py                       # 月報・年報生成
│   ├── rumor.py                         # 噂システム
│   ├── persistence/
│   │   ├── save_load.py                 # セーブ/ロード
│   │   └── migrations.py               # スキーマ移行
│   ├── ui/
│   │   ├── screens.py                   # UI画面
│   │   └── ui_helpers.py                # 表示ヘルパー
│   ├── content/
│   │   └── world_data.py               # 種族、職業、スキル定義
│   └── i18n/
│       ├── engine.py                    # 翻訳エンジン
│       ├── ja.py                        # 日本語データ
│       └── en.py                        # 英語データ
├── tests/
│   └── test_*.py                        # 各モジュールのテスト
├── .github/workflows/
│   └── test.yml                         # CI設定
├── CLAUDE.md                            # Claude Code設定
└── README.md                            # プロジェクト説明
```

## Coding Conventions

- snake_case（変数・関数）、PascalCase（クラス）
- 行の最大長: 120文字
- ユーザー向け文字列は `tr()` / `tr_term()` 経由（i18n）
- シリアライズは `to_dict()` / `from_dict()` パターン
- テストは `tests/test_<module>.py`

## Setup & Validation

```bash
# 実行（推奨）
python -m fantasy_simulator

# 実行（互換）
python main.py

# テスト
python -m pytest tests/ -v

# Lint
flake8 --max-line-length=120 --exclude=node_modules,__pycache__ .

# 一括検証
flake8 --max-line-length=120 --exclude=node_modules,__pycache__ . && python -m pytest tests/ -v
```

## NEVER

- `node_modules/`、`__pycache__/` を編集しない
- 既存のテストを削除しない
- `i18n/ja.py` / `i18n/en.py` の翻訳キー構造を壊さない
- flake8 エラーを残さない（CIで強制）
- ハードコードされたユーザー向け文字列を追加しない（`tr()` / `tr_term()` を使う）
- `persistence/save_load.py` のシリアライゼーション互換性を壊さない

## Permissions

### 自由に変更可能
- `tests/` 配下のテストファイル
- `i18n/ja.py` / `i18n/en.py` への翻訳文字列の追加
- 既存モジュール内のバグ修正・リファクタリング

### レビュー推奨
- `content/world_data.py` のゲームバランスに関わる値
- `character.py` のシリアライゼーション構造
- `simulator.py` のシミュレーションループ変更

### 変更禁止（確認必須）
- `.github/workflows/` CI設定
- `persistence/save_load.py` の保存フォーマット（後方互換性）
- `fantasy_simulator/main.py` のメニュー構造の大幅変更

## Code Examples

### キャラクター作成
```python
from fantasy_simulator.character import Character
char = Character(
    name="Aldric", age=25, gender="male", race="Human", job="Warrior",
    strength=15, intelligence=8, dexterity=12,
    wisdom=10, charisma=11, constitution=14,
)
```

### イベント生成
```python
from fantasy_simulator.events import EventSystem
es = EventSystem()
result = es.generate_random_event(world.characters, world)
# 個別イベント呼び出し
result = es.event_battle(char1, char2, world)
```

### 翻訳文字列の追加
```python
# i18n/ja.py の TEXT_JA にキーを追加
TEXT_JA: Dict[str, str] = {
    ...
    "events.new_event": "新しいイベントが発生しました: {description}",
}

# i18n/en.py の TEXT_EN にも追加
TEXT_EN: Dict[str, str] = {
    ...
    "events.new_event": "A new event occurred: {description}",
}

# 使用時 — tr() が内部で format(**kwargs) するので .format() は不要
from fantasy_simulator.i18n import tr
message = tr("events.new_event", description="...")

# 用語は TERMS_JA / TERMS_EN + tr_term()
from fantasy_simulator.i18n import tr_term
race_name = tr_term("Human")
```
