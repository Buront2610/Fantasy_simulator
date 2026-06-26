# AGENTS.md

## Project Overview

Fantasy Simulator: Python CLI世界シミュレーション（Aethoria）。Python 3.10+。ランタイムは現時点で標準ライブラリのみだが、必要に応じて外部パッケージを導入してよい。

## Architecture

- **エントリーポイント**: `python -m fantasy_simulator` → `fantasy_simulator/main.py`（互換: `python main.py`）
- **シミュレーション**: `simulation/engine.py` が月次進行を統括し、`simulation/` 配下へ責務分割済み。
  旧 root-level import の互換 alias は廃止済み。
- **キャラクター**: `character.py` は公開 `Character` ファサード。値オブジェクト・性格・表示・シリアライズ補助は
  `character_model/`、生成フローは `character_creator/` に置く
- **戦闘**: 戦闘解決と戦闘ログ read model は `combat_system/`。`combat.py` / `combat_log_index.py` は互換ラッパー
- **イベント/冒険**: `events/` がイベント生成、`adventure/` が冒険進行と保留選択を担当
- **ワールドモデル**: `world.py` が `LocationState`・world memory・state propagation を管理。
  world mixin / helper は `world_*` パッケージ群、`terrain/` が terrain/site/route/atlas layout を担当
- **UI**: `ui/screens.py` が画面制御、`ui/map_renderer.py` / `ui/atlas_renderer.py` が地図描画、
  `ui/presenters.py` / `ui/view_models.py` が表示整形を担当
- **地図投影**: renderer 非依存の地図 view model / ASCII / local map 生成は `world_map/`。UI側の
  `ui/map_renderer.py` / `ui/map_view_models.py` は互換ファサード
- **永続化**: `persistence/save_load.py`（JSON）、`persistence/migrations.py`（現行 schema v9）
- **叙述補助**: `narrative/context.py` と `narrative/template_history.py` が最小 NarrativeContext を提供

## Directory Structure

```
Fantasy_simulator/
├── main.py                              # 互換ラッパー
├── fantasy_simulator/
│   ├── __init__.py
│   ├── __main__.py                      # python -m fantasy_simulator
│   ├── main.py                          # CLIメニューループ本体
│   ├── character.py                     # Character クラス
│   ├── character_creator/               # キャラクター生成
│   ├── character_model/                 # Character 値オブジェクト・性格・表示・シリアライズ補助
│   ├── combat_system/                   # 戦闘解決・戦闘ログ read model
│   ├── world.py                         # World クラス、LocationState
│   ├── terrain/                         # TerrainMap / Site / RouteEdge / AtlasLayout
│   ├── events/                          # EventSystem クラス
│   ├── adventure/                       # Adventure クラスと進行補助
│   ├── reports/                         # 月報・年報生成
│   ├── rumor/                           # 噂システム
│   ├── world_actor/                     # キャラクター/冒険 index と actor-facing World mixin
│   ├── world_arc/                       # 長期 world arc モデルと管理
│   ├── world_calendar/                  # カレンダー解決・World mixin
│   ├── world_core/                      # World 共有 record / protocol
│   ├── world_dynamics/                  # world pressure・動的変化・era runtime
│   ├── world_event/                     # event contracts / rendering / history / log / state mutation helper
│   ├── world_history/                   # 長期履歴 retention
│   ├── world_language/                  # 言語進化・World mixin
│   ├── world_location/                  # LocationState・lookup・reference・structure helper
│   ├── world_map/                       # renderer 非依存の map view model / ASCII / local map 生成
│   ├── world_memory/                    # location memory / conflict memory mixin
│   ├── world_persistence/               # World serialization / hydration / terrain persistence
│   ├── world_state/                     # location-state decay / propagation
│   ├── world_structure/                 # load normalization / reference repair / structure rebuild
│   ├── world_topology/                  # route graph / topology query / runtime restore
│   ├── narrative/
│   │   ├── context.py                   # 最小 NarrativeContext
│   │   ├── template_history.py          # テンプレート冷却履歴
│   │   └── constants.py                 # narrative 用定数
│   ├── simulation/
│   │   ├── engine.py                    # 月次シミュレーション統括
│   │   ├── timeline.py                  # 月次進行・季節・状態遷移
│   │   ├── notifications.py             # 自動停止判定・通知
│   │   ├── event_recorder.py            # event_records 追記
│   │   ├── adventure_coordinator.py     # 冒険進行調停
│   │   └── queries.py                   # summary / story / report 参照
│   ├── persistence/
│   │   ├── save_load.py                 # セーブ/ロード
│   │   └── migrations.py               # スキーマ移行
│   ├── ui/
│   │   ├── screens.py                   # UI画面
│   │   ├── ui_helpers.py                # 表示ヘルパー
│   │   ├── map_renderer.py              # グリッド/地域/地点描画
│   │   ├── atlas_renderer.py            # アトラス表示
│   │   ├── ui_context.py                # 入出力依存コンテナ
│   │   ├── input_backend.py             # 入力抽象
│   │   ├── render_backend.py            # 出力抽象
│   │   ├── presenters.py                # 画面向け整形
│   │   └── view_models.py               # UI view model
│   ├── content/
│   │   └── world_data.py               # 種族、職業、スキル定義
│   └── i18n/
│       ├── engine.py                    # 翻訳エンジン
│       ├── ja.py                        # 日本語データ
│       └── en.py                        # 英語データ
├── tests/
│   ├── test_*.py                        # 各モジュールのテスト
│   └── support/                         # 共有テスト支援コード
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
- テストは `tests/test_<module>.py`。共有支援コードは `tests/support/`
- ルート直下の旧モジュール名互換 shim は廃止済み。新規 import は責務別パッケージを使う

## Design Conventions（設計規約）

詳細は `docs/design_philosophy_review_2026-06-10.md` §5.3 を参照。

- **契約の使い分け（DbC）**: 識別子・参照・永続化境界の不正は fail-fast（例外で拒否。例: record_id 重複、トポロジー不整合）。ゲームプレイ数値（ステータス・関係値等）はクランプして続行。迷ったら「壊れたデータが保存されうるか？」で判定し、されうるなら fail-fast 側に倒す
- **プロセス状態は必ずシリアライズ**: 複数ティックにまたがる進行中状態（補正の帳簿・アーク・保留選択・蓄積圧力）は導入初日から to_dict/from_dict に含める。一時補正は「保存値の書き換え＋後で巻き戻し」ではなく「読み出し時に合成する派生値」を優先する
- **構造はテストで守る。体験は計測で守る**: バランス・確率・進行速度に影響する変更は統計的検証（World Health Check のヘルスバンド、導入までは playtest スクリプト）を通す。バンド変更は同一 PR で理由とともに行う
- **SRP / guard の較正**: SRP は機械的な小分割ではなく凝集と変更理由の単一化で判断する。既存の complexity / size gate が過剰に分割を促している可能性も監査対象に含め、ゲート追加や閾値強化は実害・回帰検出価値・保守コストを説明できる場合に限る
- **YAGNI**: 汎用エンジン・基盤を先に作らない。1 例目は具体的に書き切り、2 例目を書くときに共通部分を抽出する

## Setup & Validation

```bash
# 開発依存のインストール
python -m pip install -e ".[dev]"

# UI extras も含めてインストールする場合
python -m pip install -e ".[dev,ui]"

# 実行（推奨）
python -m fantasy_simulator

# 実行（互換）
python main.py

# テスト
python -m pytest tests/ -v

# Lint
flake8 --max-line-length=120 --exclude=node_modules,__pycache__,.claude,.worktrees,.trunk .

# 一括検証
flake8 --max-line-length=120 --exclude=node_modules,__pycache__,.claude,.worktrees,.trunk . && python -m pytest tests/ -v

# プレイ検証（長期 world-health / balance bands）
python scripts/quality_gate.py playtest

# 品質ゲート（lint / complexity / focused mypy / playtest）
python scripts/quality_gate.py strict

# 全件検証（static checks / full pytest）
python scripts/quality_gate.py exhaustive
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
- `simulation/engine.py` / `simulation/timeline.py` の進行ループ変更
- `world.py` / `terrain/` の保存互換や world representation に関わる変更

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
