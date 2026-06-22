# Fantasy Simulator - CLAUDE.md

## Project Overview

Python CLI世界・生活シミュレーション。ファンタジー世界「Aethoria」を舞台に、キャラクターが関係を築き、旅をし、加齢し、戦い、冒険に参加する。ランタイム依存は現時点で標準ライブラリのみ。必要に応じて外部パッケージを導入してよい。

## Tech Stack

- **Language**: Python 3.10+
- **Testing**: pytest
- **Linting**: flake8 (max-line-length=120) — CIで強制（`.github/workflows/test.yml`）
- **CI**: GitHub Actions (Python 3.10/3.11/3.12) — `pip install -e ".[dev]"` → lint → focused mypy → test
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
flake8 --max-line-length=120 --exclude=node_modules,__pycache__,.claude,.worktrees,.trunk .

# 検証（Lint + テスト一括）
flake8 --max-line-length=120 --exclude=node_modules,__pycache__,.claude,.worktrees,.trunk . && python -m pytest tests/ -v

# プレイ検証（長期 world-health / balance bands）
python scripts/quality_gate.py playtest

# 品質ゲート（lint / complexity / focused mypy / playtest）
python scripts/quality_gate.py strict

# 全件検証（static checks / full pytest）
python scripts/quality_gate.py exhaustive
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
│   └── migrations.py               → セーブデータのスキーマ移行（現行 v9）
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

## Design Conventions（設計規約）

詳細は `docs/design_philosophy_review_2026-06-10.md` §5.3 を参照。

- **契約の使い分け（DbC）**: 識別子・参照・永続化境界の不正は fail-fast（例外で拒否。例: record_id 重複、トポロジー不整合）。ゲームプレイ数値（ステータス・関係値等）はクランプして続行。迷ったら「壊れたデータが保存されうるか？」で判定し、されうるなら fail-fast 側に倒す
- **プロセス状態は必ずシリアライズ**: 複数ティックにまたがる進行中状態（補正の帳簿・アーク・保留選択・蓄積圧力）は導入初日から to_dict/from_dict に含める。一時補正は「保存値の書き換え＋後で巻き戻し」ではなく「読み出し時に合成する派生値」を優先する
- **構造はテストで守る。体験は計測で守る**: バランス・確率・進行速度に影響する変更は統計的検証（World Health Check のヘルスバンド、導入までは playtest スクリプト）を通す。バンド変更は同一 PR で理由とともに行う
- **SRP / guard の較正**: SRP は機械的な小分割ではなく凝集と変更理由の単一化で判断する。既存の complexity / size gate が過剰に分割を促している可能性も監査対象に含め、ゲート追加や閾値強化は実害・回帰検出価値・保守コストを説明できる場合に限る
- **YAGNI**: 汎用エンジン・基盤を先に作らない。1 例目は具体的に書き切り、2 例目を書くときに共通部分を抽出する
