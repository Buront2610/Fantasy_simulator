# Fantasy Simulator - CLAUDE.md

## Project Overview

Python CLI世界・生活シミュレーション。ファンタジー世界「Aethoria」を舞台に、キャラクターが関係を築き、旅をし、加齢し、戦い、冒険に参加する。ランタイム依存は現時点で標準ライブラリのみ。必要に応じて外部パッケージを導入してよい。

## Tech Stack

- **Language**: Python 3.10+
- **Testing**: pytest
- **Linting**: flake8 (max-line-length=120) — CIで強制（`.github/workflows/test.yml`）
- **CI**: GitHub Actions (Python 3.10/3.11/3.12) — `pip install pytest flake8` → lint → test
- **Localization**: 自前i18nシステム（英語/日本語）

## Commands

```bash
# 実行
python main.py

# テスト
python -m pytest tests/ -v

# Lint
flake8 --max-line-length=120 --exclude=node_modules,__pycache__ .

# 検証（Lint + テスト一括）
flake8 --max-line-length=120 --exclude=node_modules,__pycache__ . && python -m pytest tests/ -v
```

## Architecture

```
main.py              → CLIエントリーポイント・メニューループ
├── screens.py       → UI画面（メニュー、セットアップ、結果表示）
├── ui_helpers.py    → 表示ユーティリティ（色付き出力、メニュー選択）
├── simulator.py     → 年次シミュレーション管理
│   ├── events.py    → イベント生成・解決（出会い、旅、発見、訓練、戦闘、結婚、死亡）
│   └── adventure.py → 複数ステップの冒険進行
├── world.py         → ワールドマップ（5x5グリッド）、ロケーション、キャラ管理
├── world_data.py    → ゲームコンテンツ定義（種族、職業、スキル、場所）
├── character.py     → キャラクターモデル（能力値、スキル、関係性）
├── character_creator.py → キャラクター生成（ランダム、テンプレート、対話式）
├── save_load.py     → JSON形式のセーブ/ロード
└── i18n.py          → ローカライゼーション（600+翻訳文字列）
```

## Coding Conventions

- **行の最大長**: 120文字（flake8で強制、CIで検証）
- **命名規則**: snake_case（変数・関数）、PascalCase（クラス）、UPPER_SNAKE_CASE（定数）
- **インポート順**: 標準ライブラリ → サードパーティ → ローカル
- **ローカライゼーション**: ユーザー向け文字列は `i18n.py` の `tr()` / `tr_term()` 経由で取得。辞書は `_TEXT` / `_TERMS`。ハードコードしない
- **シリアライゼーション**: `to_dict()` / `from_dict()` パターンでJSON化
- **テスト**: 各モジュールに対応するテストファイルが `tests/test_<module>.py` に存在。共有fixtureは各テストファイル内で定義（conftest.pyは現在sys.path設定のみ）

## NEVER

- `node_modules/`、`__pycache__/`、`.pytest_cache/` を編集・コミットしない
- `.env` ファイルをコミットしない
- 既存のテストを削除しない（修正・追加のみ）
- `i18n.py` の翻訳キー構造を壊さない
- `console.log` や `print` デバッグ文を本番コードに残さない
- flake8 のルールを無視しない（`# noqa` は最終手段、理由をコメントで説明すること）

## Testing Guidelines

- 新しい機能やバグ修正には対応するテストを追加する
- テストは `tests/test_<module>.py` の命名規則に従う
- テストは独立して実行可能であること（順序依存しない）
- モック使用時はパッチ対象を正確に指定する（`unittest.mock.patch`）
- ローカルで `flake8` + `pytest` を通してからコミットする（CIと同一コマンド）

## Localization Rules

- `_TEXT` / `_TERMS` はlocale-first構造: `{"ja": {"key": "値"}, "en": {"key": "value"}}`
- 新しい文字列は各locale辞書にキーを追加する
- 翻訳キーはドット区切りの階層構造（例: `"events.battle.victory"`）
- 英語と日本語の両方を必ず追加する
- `tr("key", **kwargs)` で取得（内部で `format(**kwargs)` 済み、`.format()` 連鎖は不要）。フォールバックは英語
- 用語は `tr_term("term")`

## Design Principles

- 冒険はメインシミュレーション内に統合（別ゲームモードにしない）
- プレイヤーの介入は重要な瞬間に限定（選択的介入）
- 変更はインクリメンタルかつモジュラーに
- 可読性と実験しやすさを重視（完璧なリアリズムより）
