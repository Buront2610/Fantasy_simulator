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
# 実行（推奨）
python -m fantasy_simulator

# 実行（互換ラッパー）
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
main.py                              → 互換ラッパー（fantasy_simulator.main を呼ぶだけ）
fantasy_simulator/
├── __main__.py                      → python -m fantasy_simulator エントリーポイント
├── main.py                          → CLIメニューループ本体
├── simulator.py                     → 後方互換ラッパー（実体は simulation/）
├── simulation/
│   ├── engine.py                    → 月次シミュレーション統括
│   ├── timeline.py                  → 月次進行・季節・状態遷移
│   ├── notifications.py             → 自動停止判定・通知
│   ├── event_recorder.py            → event_records 記録
│   ├── adventure_coordinator.py     → 冒険進行調停
│   └── queries.py                   → summary / story / report 参照
├── events.py                        → イベント生成・解決
├── adventure.py                     → 複数ステップの冒険進行と保留選択
├── world.py                         → ワールド、LocationState、world memory、terrain連携
├── terrain.py                       → TerrainMap / Site / RouteEdge / AtlasLayout
├── character.py                     → キャラクターモデル（能力値、スキル、関係性）
├── character_creator.py             → キャラクター生成（ランダム、テンプレート、対話式）
├── reports.py                       → 月報・年報のビュー生成
├── rumor.py                         → 噂の生成・ライフサイクル
├── narrative/
│   ├── context.py                   → 最小 NarrativeContext
│   ├── template_history.py          → テンプレート冷却履歴
│   └── constants.py                 → narrative 用定数
├── persistence/
│   ├── save_load.py                 → JSON形式のセーブ/ロード
│   └── migrations.py               → セーブデータのスキーマ移行（現行 v7）
├── ui/
│   ├── screens.py                   → UI画面（メニュー、セットアップ、結果表示）
│   ├── ui_helpers.py                → 表示ユーティリティ
│   ├── ui_context.py                → UIContext 依存コンテナ
│   ├── input_backend.py             → 入力抽象
│   ├── render_backend.py            → 出力抽象
│   ├── map_renderer.py              → グリッド/地域/地点描画
│   ├── atlas_renderer.py            → アトラス描画
│   ├── presenters.py                → 画面向け整形
│   └── view_models.py               → UI view model
├── content/
│   └── world_data.py                → ゲームコンテンツ定義（種族、職業、スキル、場所）
└── i18n/
    ├── engine.py                    → ローカライゼーションエンジン（tr, tr_term, set_locale）
    ├── ja.py                        → 日本語テキスト・用語
    └── en.py                        → 英語テキスト・用語
```

## Coding Conventions

- **行の最大長**: 120文字（flake8で強制、CIで検証）
- **命名規則**: snake_case（変数・関数）、PascalCase（クラス）、UPPER_SNAKE_CASE（定数）
- **インポート順**: 標準ライブラリ → サードパーティ → ローカル
- **ローカライゼーション**: ユーザー向け文字列は `i18n/engine.py` の `tr()` / `tr_term()` 経由で取得。テキストは `i18n/ja.py` / `i18n/en.py` に分離。ハードコードしない
- **シリアライゼーション**: `to_dict()` / `from_dict()` パターンでJSON化
- **テスト**: 各モジュールに対応するテストファイルが `tests/test_<module>.py` に存在。共有fixtureは各テストファイル内で定義（conftest.pyは現在sys.path設定のみ）

## NEVER

- `node_modules/`、`__pycache__/`、`.pytest_cache/` を編集・コミットしない
- `.env` ファイルをコミットしない
- 既存のテストを削除しない（修正・追加のみ）
- `i18n/ja.py` / `i18n/en.py` の翻訳キー構造を壊さない
- `console.log` や `print` デバッグ文を本番コードに残さない
- flake8 のルールを無視しない（`# noqa` は最終手段、理由をコメントで説明すること）

## Testing Guidelines

- 新しい機能やバグ修正には対応するテストを追加する
- テストは `tests/test_<module>.py` の命名規則に従う
- テストは独立して実行可能であること（順序依存しない）
- モック使用時はパッチ対象を正確に指定する（`unittest.mock.patch`）
- ローカルで `flake8` + `pytest` を通してからコミットする（CIと同一コマンド）

## Localization Rules

- テキストは `i18n/ja.py` (`TEXT_JA`, `TERMS_JA`) と `i18n/en.py` (`TEXT_EN`, `TERMS_EN`) に分離
- 新しい文字列は `ja.py` と `en.py` の両方に追加する
- 翻訳キーはドット区切りの階層構造（例: `"events.battle.victory"`）
- 英語と日本語の両方を必ず追加する
- `tr("key", **kwargs)` で取得（内部で `format(**kwargs)` 済み、`.format()` 連鎖は不要）。フォールバックは英語
- 用語は `tr_term("term")`

## Design Principles

- 冒険はメインシミュレーション内に統合（別ゲームモードにしない）
- プレイヤーの介入は重要な瞬間に限定（選択的介入）
- 変更はインクリメンタルかつモジュラーに
- terrain/site/route と atlas UI は導入済みだが、worldgen PoC は未完了
- 可読性と実験しやすさを重視（完璧なリアリズムより）
