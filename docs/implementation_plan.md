# Fantasy Simulator vNext 実装計画書

**プロジェクト名**: Fantasy Simulator  
**世界名**: Aethoria（エイソリア）  
**版**: Implementation Plan v1.0  
**最終更新**: 2026-03-22  
**位置づけ**: 本書は `docs/next_version_plan.md`（設計書）および詳細レビューフィードバックに基づき、vNext 開発の全工程・PR 分割・migration 方針・ID 規則・通知密度・location 参照修正方針までを**公式実装計画として**明文化したものです。

> **注意（設計書との関係）**: `docs/next_version_plan.md` §15 の migration 例（v1〜v4）は設計上の参考例です。**正式な migration chain・ID 規則・location 参照修正方針は本計画書に従ってください。** 設計書側にも「正式は implementation_plan.md に従う」旨の但し書きを追加する PR（後述 PR-0）を推奨します。

---

## 0. 本文書の目的

本書は次の目的を同時に満たす。

1. **Safety Invariant の確立**  
   `character.location_id` は常に有効な `LocationState.id` を参照する。これを第 1 目標とし、以後のすべての実装判断はこの不変条件を優先する。

2. **移行方針の確定**  
   現行コードの `Location`（名前文字列）から `LocationState`（id ベース）への一括移行方針を定め、一時的互換ラッパーの扱いを明記する。

3. **PR 分割と必須作業リストの確定**  
   各フェーズで何を作り、どこで合流するかを具体的に示す。

4. **過去の誤りへの対応明記**  
   `LocationState` 設計ズレ・旧 migration 例・互換プロパティ問題・イベント密度混在などを整理し、再発を防ぐ。

---

## 1. Safety Invariant（第1目標）

```
Invariant SI-1: character.location_id は常に有効な LocationState.id を参照する。
Invariant SI-2: world.get_location_by_id(character.location_id) は None を返さない。
Invariant SI-3: すべての WorldEventRecord.location_id は有効な LocationState.id を参照する（または None）。
```

これらは以下のすべての PR でテストによって保証する。違反したコードはレビューで差し戻す。

---

## 2. 過去の誤りと対応方針

| 誤り・問題 | 原因 | 本計画での対応 |
|---|---|---|
| `LocationState` 設計ズレ（`id` なし案など） | 設計書初稿が `name` 参照を引き継いでいた | §3 で `id`/`canonical_name` を正式定義 |
| 設計書 §15 migration 例が旧案（`Location` 互換混在） | 設計書が実装コードと非同期に進化 | 本計画書の migration chain を正式とし、設計書には但し書き追加 |
| `character.location`（str）の互換ラッパー温存 | 段階的移行のために残した互換プロパティが技術的負債化 | PR-3 で一括置換。互換ラッパーは PR-3 完了後に削除（§6 参照） |
| イベント密度と通知密度の混在 | 内部生成頻度と UI 通知頻度が同一変数で管理されていた | §8 で分離方針を定義 |
| 旧セーブの `location` フィールドが名前文字列 | `character.location = "Aethoria Capital"` 形式が長期運用された | §5 の name→id 対応表で migration v2 にて一括変換 |

---

## 3. LocationState 正式定義

### 3.1 クラス定義

```python
@dataclass
class LocationState:
    id: str               # 不変の識別子 例: "loc_aethoria_capital"
    canonical_name: str   # 表示用正式名 例: "Aethoria Capital"
    description: str
    region_type: str
    x: int
    y: int
    prosperity: int        # 0-100
    safety: int            # 0-100
    mood: int              # 0-100
    danger: int            # 0-100
    traffic: int           # 0-100
    rumor_heat: int        # 0-100
    road_condition: int    # 0-100
    visited: bool = False
    controlling_faction_id: str | None = None
    recent_event_ids: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)      # TODO: 将来 LocationAlias 型（設計書 §6.1）を導入する場合はここを置き換える
    memorial_ids: list[str] = field(default_factory=list)
```

### 3.2 ID 規則（ID Convention）

```
ルール: id = "loc_" + (canonical_name を小文字にし、空白・特殊文字をアンダースコアで置換した slug)
例:
  "Aethoria Capital"  → "loc_aethoria_capital"
  "Frostpeak Summit"  → "loc_frostpeak_summit"
  "The Grey Pass"     → "loc_the_grey_pass"
  "Goblin Warrens"    → "loc_goblin_warrens"
  "Sunken Ruins"      → "loc_sunken_ruins"
```

`loc_` プレフィックスにより、他の種別の ID（`char_`, `quest_` 等）との衝突を防ぎ、文字列を見ただけで地点 ID と分かる。

**ルール: built-in 地点の id は `DEFAULT_LOCATIONS` で固定する。一度確定した id は変更しない。**

### 3.3 DEFAULT_LOCATIONS の更新形式

現行の `(name, description, region_type, x, y)` タプルを以下に拡張する。

```python
# (id, canonical_name, description, region_type, x, y)
DEFAULT_LOCATIONS = [
    ("loc_frostpeak_summit",   "Frostpeak Summit",   "A jagged mountain crowned with eternal ice.",                  "mountain", 0, 0),
    ("loc_the_grey_pass",      "The Grey Pass",       "A treacherous alpine pass haunted by wind spirits.",           "mountain", 1, 0),
    ("loc_skyveil_monastery",  "Skyveil Monastery",   "A cliffside monastery where monks study the ley-lines.",       "village",  2, 0),
    ("loc_ironvein_mine",      "Ironvein Mine",        "A deep mine rich in enchanted ore — and old curses.",          "dungeon",  3, 0),
    ("loc_stormwatch_keep",    "Stormwatch Keep",      "A fortress overlooking the northern sea.",                     "mountain", 4, 0),
    ("loc_thornwood",          "Thornwood",            "A dense forest that hums with restless magic.",                "forest",   0, 1),
    ("loc_ashenvale",          "Ashenvale",            "Charred woodland recovering from a decade-old wildfire.",      "forest",   1, 1),
    ("loc_silverbrook",        "Silverbrook",          "A prosperous trading town built on a swift silver river.",     "city",     2, 1),
    ("loc_goblin_warrens",     "Goblin Warrens",       "A network of tunnels teeming with mischievous creatures.",     "dungeon",  3, 1),
    ("loc_eastwatch_tower",    "Eastwatch Tower",      "A lone watchtower staffed by a rotating ranger garrison.",     "village",  4, 1),
    ("loc_elderroot_forest",   "Elderroot Forest",     "An ancient forest whose trees remember the Cataclysm.",        "forest",   0, 2),
    ("loc_millhaven",          "Millhaven",            "A quiet farming village known for its legendary apple wine.",  "village",  1, 2),
    ("loc_aethoria_capital",   "Aethoria Capital",     "The grand capital — heart of trade, politics, and intrigue.",  "city",     2, 2),
    ("loc_sunken_ruins",       "Sunken Ruins",         "Ruins of a pre-Cataclysm city, half-swallowed by the earth.", "dungeon",  3, 2),
    ("loc_saltmarsh",          "Saltmarsh",            "A fishing village where sailors whisper of sea monsters.",     "village",  4, 2),
    ("loc_dragonbone_ridge",   "Dragonbone Ridge",     "A ridge littered with the bones of ancient dragons.",          "mountain", 0, 3),
    ("loc_dusty_crossroads",   "Dusty Crossroads",     "A well-worn junction where merchants rest and rumours spread.", "plains",  1, 3),
    ("loc_hearthglow_town",    "Hearthglow Town",      "A warm, welcoming town renowned for its healers' guild.",      "city",     2, 3),
    ("loc_mirefen_swamp",      "Mirefen Swamp",        "A murky swamp hiding both treasure and terrible dangers.",     "dungeon",  3, 3),
    ("loc_dawnport",           "Dawnport",             "A busy harbour city that never truly sleeps.",                 "city",     4, 3),
    ("loc_sunbaked_plains",    "Sunbaked Plains",      "Vast golden plains scorched by an unrelenting sun.",           "plains",   0, 4),
    ("loc_sandstone_outpost",  "Sandstone Outpost",    "A small desert outpost at the edge of the known world.",       "village",  1, 4),
    ("loc_the_verdant_vale",   "The Verdant Vale",     "A lush valley sheltered from harsh winds — a true paradise.", "village",  2, 4),
    ("loc_obsidian_crater",    "Obsidian Crater",      "A massive crater from the Cataclysm, still faintly glowing.", "dungeon",  3, 4),
    ("loc_coral_cove",         "Coral Cove",           "A hidden cove home to a secretive community of sea-mages.",    "city",     4, 4),
]
```

---

## 4. Character.location_id への移行

### 4.1 移行前後の比較

| 項目 | 移行前（現行） | 移行後（vNext） |
|---|---|---|
| フィールド名 | `character.location: str` | `character.location_id: str` |
| 値の型 | 地点名（例: `"Aethoria Capital"`） | 地点 ID（例: `"loc_aethoria_capital"`） |
| 参照先 | `World._location_name_index[name]` | `World.get_location_by_id(id)` |
| 表示用の名前取得 | `character.location` そのもの | `world.get_location_by_id(character.location_id).canonical_name` |

### 4.2 互換ラッパーを置かない方針

**`character.location` 互換プロパティは PR-3 では追加しない。**

以前の計画では互換プロパティを挟んで段階的に移行する案があったが、これは安全でない。理由：

- 現行コードの `character.location` は**場所名文字列**（例: `"Aethoria Capital"`）を返すことを前提とする
- 互換プロパティが `location_id`（例: `"loc_aethoria_capital"`）を返せば、`character.location == "Aethoria Capital"` という比較が静かに壊れる
- 互換プロパティが `canonical_name` を返す場合でも、`_location_name_index` を引く旧コードやシリアライザが壊れる
- どちらのフォールバックでも「透過」にならない

**正しい方針（PR-3 の Definition of Done）**:

1. `character.location_id: str` を正式フィールドとする
2. PR-3 内で `\.location\b` を grep して **全参照を同一 PR で置換**する:
   - ID 比較・インデックス参照 → `character.location_id`
   - 表示・ログ出力 → `world.get_location_by_id(character.location_id).canonical_name`
3. **旧 `character.location` 参照ゼロ**を PR-3 のマージ条件とする
4. 互換プロパティは追加しない

これにより意味の食い違いが起きない。

---

## 5. Migration Chain（正式版）

### 5.1 バージョン表

| Version | 変更内容 | 対応 PR |
|---|---|---|
| v0 | schema_version なし（旧形式） | — |
| v1 | `schema_version: 1` 追加のみ | PR-2 |
| v2 | `Character.location`（name str）→ `Character.location_id`（id str）一括変換 | PR-3 |
| v3 | `LocationState` 正式導入 + `WorldEventRecord` 導入 | PR-3（v2 と同一 PR） |
| v4 | `Relationship` 構造化 + `ReputationEntry` 導入 | Phase 3 の PR |

> **設計書 §15 の migration 例は旧案（v1=schema_version + `job→adventure_job`, v2=LocationState, v3=Relationship, v4=dying）です。本計画書の上記テーブルを正式とします。** 主な差分: `job→adventure_job` は採用しない（設計書 §15.3 の v1 の記述は概念例）。v2 で location 参照を一括修正する。v3 で `LocationState` + `WorldEventRecord` を同時導入する。

### 5.2 Migration 関数の骨格

```python
# persistence/migrations.py

CURRENT_VERSION = 3

MIGRATIONS: dict[int, Callable[[dict], dict]] = {
    1: migrate_v0_to_v1,  # schema_version 追加
    2: migrate_v1_to_v2,  # location name → location_id
    3: migrate_v2_to_v3,  # LocationState 正式化 + WorldEventRecord 導入
}


def apply_migrations(data: dict) -> dict:
    version = data.get("schema_version", 0)
    for target_version in range(version + 1, CURRENT_VERSION + 1):
        migrate_fn = MIGRATIONS.get(target_version)
        if migrate_fn is None:
            raise MigrationError(f"No migration function for version {target_version}")
        data = migrate_fn(data)
    return data
```

### 5.3 migrate_v1_to_v2 — location name → location_id の一括変換

```python
# 旧セーブの location フィールド（名前文字列）を id へ変換する
LOCATION_NAME_TO_ID: dict[str, str] = {
    "Frostpeak Summit":  "loc_frostpeak_summit",
    "The Grey Pass":     "loc_the_grey_pass",
    "Skyveil Monastery": "loc_skyveil_monastery",
    "Ironvein Mine":     "loc_ironvein_mine",
    "Stormwatch Keep":   "loc_stormwatch_keep",
    "Thornwood":         "loc_thornwood",
    "Ashenvale":         "loc_ashenvale",
    "Silverbrook":       "loc_silverbrook",
    "Goblin Warrens":    "loc_goblin_warrens",
    "Eastwatch Tower":   "loc_eastwatch_tower",
    "Elderroot Forest":  "loc_elderroot_forest",
    "Millhaven":         "loc_millhaven",
    "Aethoria Capital":  "loc_aethoria_capital",
    "Sunken Ruins":      "loc_sunken_ruins",
    "Saltmarsh":         "loc_saltmarsh",
    "Dragonbone Ridge":  "loc_dragonbone_ridge",
    "Dusty Crossroads":  "loc_dusty_crossroads",
    "Hearthglow Town":   "loc_hearthglow_town",
    "Mirefen Swamp":     "loc_mirefen_swamp",
    "Dawnport":          "loc_dawnport",
    "Sunbaked Plains":   "loc_sunbaked_plains",
    "Sandstone Outpost": "loc_sandstone_outpost",
    "The Verdant Vale":  "loc_the_verdant_vale",
    "Obsidian Crater":   "loc_obsidian_crater",
    "Coral Cove":        "loc_coral_cove",
}


def _name_to_id(name: str) -> str:
    """name → id を対応表で解決。不明な場合は loc_ + slug フォールバック。"""
    if name in LOCATION_NAME_TO_ID:
        return LOCATION_NAME_TO_ID[name]
    # フォールバック: "loc_" + slug 変換（小文字・空白→アンダースコア・特殊文字除去）
    # built-in 地点は必ず対応表で解決されるため、このパスはユーザー追加地点のみ
    import re
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return f"loc_{slug}"


def migrate_v1_to_v2(data: dict) -> dict:
    data = dict(data)
    data["schema_version"] = 2
    for char_data in data.get("characters", []):
        old_location = char_data.pop("location", "loc_aethoria_capital")
        char_data["location_id"] = _name_to_id(old_location)
    return data
```

> **slug はフォールバックのみ。** built-in 地点は必ず `LOCATION_NAME_TO_ID` 対応表で変換する。対応表に存在しない名前（ユーザー追加地点など）のみ slug を使う。

### 5.4 旧セーブ互換の保証範囲

| 保証する | 保証しない |
|---|---|
| schema_version=0〜2 の旧セーブが正常に読み込める | migration 前に `character.location_id` への直接アクセス |
| migration 後に SI-1〜SI-3 が成立する | 旧セーブを migration なしで使うことの動作正確性 |
| `LOCATION_NAME_TO_ID` の全 built-in 地点を網羅 | ユーザー追加地点のフォールバック slug が完全一致すること |

---

## 6. location 参照修正方針

### 6.1 基本方針

**一気に参照置換する。段階的な名前参照残存は認めない。**

現行コードで `character.location`（名前文字列）を参照している箇所をすべて PR-3 で `character.location_id` に一括置換する。

### 6.2 影響ファイル一覧（現行コード調査結果）

| ファイル | 対象コード | 修正内容 |
|---|---|---|
| `character.py` | `self.location: str = location` | `self.location_id: str = location_id`（`__init__` 引数も `location_id` に変更） |
| `character.py` | `to_dict()` の `"location": self.location` | `"location_id": self.location_id` |
| `character.py` | `from_dict()` の `location=data.get("location", ...)` | `location_id=data.get("location_id", "loc_aethoria_capital")` |
| `world.py` | `character.location` 参照（`add_character`, `get_characters_at_location` 等） | `character.location_id` に変更 |
| `world.py` | `_location_name_index` → `_location_id_index` | id ベースのインデックスに変更 |
| `world.py` | `get_location_by_name()` | `get_location_by_id()` を追加。`get_location_by_name()` は deprecated |
| `events.py` | `character.location` 参照 | `character.location_id` に変更 |
| `adventure.py` | `character.location` 参照 | `character.location_id` に変更 |
| `screens.py` | `character.location` 表示 | `world.get_location_by_id(character.location_id).canonical_name` 経由に変更 |
| `character_creator.py` | `location="Aethoria Capital"` デフォルト | `location_id="loc_aethoria_capital"` に変更 |

### 6.3 置換の順序

1. `world_data.py`: `DEFAULT_LOCATIONS` を id 付き形式（`loc_` プレフィックス）に更新
2. `world.py`: `LocationState` 定義、`_location_id_index`、`get_location_by_id()` 追加
3. `character.py`: `location: str` → `location_id: str`（互換プロパティは追加しない）
4. 上記以外の参照ファイル（`events.py`, `adventure.py`, `screens.py`, `character_creator.py`）: 一括修正
5. テスト: 全テストが通過することを確認
6. grep で `character\.location\b`（`location_id` を除く）が残っていないことを確認 → PR-3 マージ条件

---

## 7. Favorite / Spotlight / Playable の先行導入

**月報（Phase 2）前に PR-2.5 として導入する。**

これらのフラグなしに月報の「注目人物」欄を実装できないため、Phase 1 完了直後に以下を追加する。

```python
# character.py へ追加
favorite: bool = False       # プレイヤーが手動でマーク。月報に必ず掲載
spotlighted: bool = False    # 自動または手動の一時注目。dying 時に高優先通知
playable: bool = False       # 主人公モード中フラグ。方針選択をプレイヤーが担う
```

### 7.1 各フラグの意味と使用箇所

| フラグ | セット主体 | 効果 |
|---|---|---|
| `favorite` | プレイヤー手動 | 月報必掲載・年報特記・通知優先度 +20 |
| `spotlighted` | プレイヤー / 自動 | dying 時通知優先度 +40・月報に行動詳細 |
| `playable` | プレイヤー手動 | 冒険方針をプレイヤーが直接選択（§9.3 設計書参照） |

### 7.2 セーブ互換

- `to_dict()` / `from_dict()` に追加。デフォルト値は `False`。
- migration 不要（旧セーブで欠損時は `False` として読み込む）。

---

## 8. イベント密度と通知密度の分離

### 8.1 問題の整理

現行コードでは「イベントが生成される頻度」と「プレイヤーに通知する頻度」が実質的に同一である。これにより、シミュレーション内部の豊かさと UI のノイズがトレードオフになっている。

### 8.2 分離方針

```
内部イベント密度（simulation density）: シミュレーション内で月次に生成するイベントの数と種類
通知密度（notification density）:       プレイヤーの UI に表示・中断を引き起こすイベントの閾値
```

これらを独立したパラメータとして管理する。

```python
# simulator.py または config.py
SIMULATION_DENSITY = {
    "minor_events_per_month_per_char": 0.3,  # NPC1体あたり月間軽微イベント期待値
    "major_events_per_month_per_char": 0.05, # 重大イベント期待値
}

NOTIFICATION_THRESHOLDS = {
    "favorite_any":       True,   # favorite のいかなるイベントも通知
    "spotlight_serious":  True,   # spotlighted が serious 以上で通知
    "auto_pause_dying":   True,   # dying 発生で自動停止
    "auto_pause_months":  6,      # 最大 N ヶ月で一度通知
    "rumor_high_heat":    70,     # rumor_heat >= 70 で地域通知
}
```

### 8.3 月報・年報への反映

- 月報は `NOTIFICATION_THRESHOLDS` に従い生成（内部イベントをすべて出力しない）。
- 内部 `WorldEventRecord` はすべて記録するが、月報への掲載は重要度フィルタを通す。
- 詳細ログ（全イベント）はデバッグモードまたは「詳細表示」で閲覧可能とする。

### 8.4 UI 連携規約

- `WorldEventRecord` は世界側の正規イベント表現とし、保存・通知密度判定・月報/年報集計の基準にする。
- UI / report 層が `EventRecord` 等の表示用レコードを用いる場合、それは `WorldEventRecord` から導出する非永続の view model とし、新たな正規スキーマは増やさない。
- `ui/` パッケージ化、renderer / input interface 定義、`screens.py` / `ui_helpers.py` の facade 化は PR-1〜PR-3 と並行して先行着手してよい。
- ただし `location_id` / `WorldEventRecord` を前提とする表示刷新（マップ再設計、月報/年報、イベントフィルタ UI）は PR-3 完了後に切り替える。
- 詳細な画面刷新方針は `docs/ui_renovation_plan.md` に従う。

---

## 9. PR 分割計画（必須 PR リスト）

### PR-0（推奨・任意）: 設計書但し書き追加

- `docs/next_version_plan.md` §15 に「正式な migration chain・location 参照修正方針は `docs/implementation_plan.md` に従う」旨の但し書きを追加
- コード変更なし

### PR-1: パッケージ構造化

**ゴール**: ロジック変更なし、全テスト通過  
**作業**:
- `requirements-dev.txt` 追加（`pytest>=7.0`, `hypothesis>=6.0`）
- `docs/` 以下の README 更新（任意）
- CI 通過確認

**マージ条件**: 全テスト通過、flake8 通過

---

### PR-2: schema_version と migration 基盤 ✅ 完了（PR #11 にて実装）

**ゴール**: 旧セーブの schema_version 欠損を安全に扱える
**作業**:
- [x] `persistence/migrations.py`（または `migrations.py`）を新規作成
  - `CURRENT_VERSION = 2`
  - `migrate_v1_to_v2`（schema_version 追加 + location name→id 変換）
  - `migrate(data)` 関数（未来バージョン拒否を含む）
- [x] `save_load.py` の `load_simulation` で `migrate` を呼び出す
- [x] テスト: `test_migrations.py` にて v1 セーブの読み込みテスト + 未来バージョン拒否テスト

**マージ条件**: 全テスト通過、migration chain のテスト存在

---

### PR-2.5: Favorite / Spotlight / Playable フラグ追加

**ゴール**: 月報実装前に注目フラグを安定させる  
**作業**:
- `character.py` に `favorite`, `spotlighted`, `playable` フラグ追加
- `to_dict()` / `from_dict()` に対応追加（デフォルト False）
- テスト: `test_character.py` にフラグの serialize/deserialize テスト追加

**マージ条件**: 全テスト通過、旧セーブ互換確認（デフォルト False）

---

### PR-3: LocationState 導入 + location 参照一括修正 — 部分完了（PR #11 にて Stage 1-3 実装）

**ゴール**: SI-1 〜 SI-3 を確立する。これが Phase 1 の最重要 PR。
**作業**:

1. [x] `world_data.py`: `DEFAULT_LOCATIONS` を `(id, canonical_name, description, region_type, x, y)` 形式に更新（`loc_` プレフィックス付き id）
2. `world.py`:
   - [ ] `Location` dataclass → `LocationState` dataclass（§3.1 の定義：prosperity, safety, mood 等の状態量追加）
   - [x] `_location_id_index: Dict[str, Location]` 追加
   - [x] `get_location_by_id(id: str)` 追加
   - [x] `location_name(location_id)` 追加（フォールバック付き）
   - [ ] `render_map()` に danger/safety_label/traffic 簡易表示追加（設計書 §18.2）
3. [x] `character.py`:
   - `location: str` → `location_id: str`（互換プロパティは追加しない）
4. [ ] `character_creator.py`: `location="Aethoria Capital"` → `location_id="loc_aethoria_capital"`（変更不要だった — character_creator.py に location 参照なし）
5. [x] `events.py` / `adventure.py` / `screens.py`: `character.location` → `character.location_id` に一括置換 + `WorldEventRecord` 導入
6. [x] `migrations.py`: `CURRENT_VERSION = 2`、`migrate_v1_to_v2`（location name→id 変換）追加

**テスト要件**:
- [x] migration v1→v2 のテスト（全 built-in 地点名が正しく `loc_` 付き id に変換される）
- [x] 旧セーブ（`location: "Aethoria Capital"` 形式）の読み込みテスト
- [ ] SI-1 〜 SI-3 の不変条件テスト（全キャラの `location_id` が有効 id を参照する）— `LocationState` 完全導入後に追加

**マージ条件**:
- 全テスト通過、SI-1 〜 SI-3 のテストが存在、flake8 通過
- `character\.location\b`（`location_id` を除く）の grep 結果がゼロ（旧参照ゼロ）

**残作業**: `Location` → `LocationState` への完全移行（状態量フィールド追加）、render_map 拡張

---

### Phase 2 以降の PR（参考）

| PR | 内容 | 依存 |
|---|---|---|
| PR-4 | 月報 / 年報 / 復帰サマリー + UI report adapter | PR-2.5, PR-3 |
| PR-5 | Rumor / reliability / 通知密度分離 | PR-4 |
| PR-6 | 条件付き自動進行（AUTO_PAUSE_PRIORITIES） | PR-4 |
| PR-7 | Relationship 構造化 + ReputationEntry | PR-3 |
| PR-8 | dying / rescue / 死の段階化 | PR-7 |
| PR-9 | AdventureRun パーティ化 + 能力値依存 outcome | PR-8 |
| PR-10 | live trace + memorial + alias | PR-9 |
| PR-11 | map renderer 初期 AA 版 | PR-10 |

---

## 10. 必須テストサマリー

各 PR マージ前に以下のテストが存在し、通過することを確認する。

### 10.1 Safety Invariant テスト（PR-3 以降必須）

```python
# tests/test_invariants.py

def test_si1_all_characters_have_valid_location_id(world_fixture):
    """SI-1: 全キャラの location_id が有効な LocationState.id を参照する。"""
    for char in world_fixture.characters:
        assert world_fixture.get_location_by_id(char.location_id) is not None, (
            f"Character {char.name!r} has invalid location_id {char.location_id!r}"
        )


def test_si2_location_never_returns_none_for_valid_char(world_fixture):
    """SI-2: get_location_by_id は有効な location_id に対して None を返さない。"""
    for char in world_fixture.characters:
        loc = world_fixture.get_location_by_id(char.location_id)
        assert loc is not None


def test_si3_world_event_records_location_id(world_fixture):
    """SI-3: WorldEventRecord.location_id は有効 id または None。"""
    valid_ids = {loc.id for loc in world_fixture.grid.values()}
    for record in world_fixture.event_records:
        if record.location_id is not None:
            assert record.location_id in valid_ids, (
                f"WorldEventRecord has invalid location_id {record.location_id!r}"
            )
```

### 10.2 Migration テスト（PR-2, PR-3 必須）

```python
# tests/test_migrations.py

def test_migrate_v0_adds_schema_version():
    data = {"characters": [], "world": {}}
    result = apply_migrations(data)
    assert result["schema_version"] == CURRENT_VERSION


def test_migrate_v1_to_v2_converts_all_builtin_locations():
    """全 built-in 地点名が正しく id に変換される。"""
    # 各 built-in 地点名だけを持つ最小キャラクターデータを生成
    char_data = [{"name": "char", "location": name} for name in LOCATION_NAME_TO_ID.keys()]
    data = {"schema_version": 1, "characters": char_data}
    result = migrate_v1_to_v2(data)
    for char, (name, expected_id) in zip(result["characters"], LOCATION_NAME_TO_ID.items()):
        assert char["location_id"] == expected_id, (
            f"Location {name!r} should map to {expected_id!r}, got {char['location_id']!r}"
        )


def test_old_save_roundtrip(tmp_path):
    """旧セーブ（schema_version なし）が正常に読み込める。"""
    # 旧セーブ形式: location フィールドに場所名文字列
    old_save = {
        "characters": [{"name": "Aldric", "location": "Aethoria Capital"}],
        "world": {"year": 1000},
    }
    path = tmp_path / "old_save.json"
    path.write_text(json.dumps(old_save))
    sim = load_simulation(str(path))
    assert sim is not None
    char = sim.world.characters[0]
    assert char.location_id == "loc_aethoria_capital"
```

### 10.3 Favorite / Spotlight / Playable テスト（PR-2.5 必須）

```python
# tests/test_character.py への追記

def test_favorite_flag_serialization():
    # 最小限の必須フィールドでキャラクターを生成
    char = Character(
        name="Aldric", age=25, gender="male", race="Human", job="Warrior",
        favorite=True,
    )
    d = char.to_dict()
    assert d["favorite"] is True
    char2 = Character.from_dict(d)
    assert char2.favorite is True


def test_flags_default_false_on_old_save():
    """旧セーブに favorite/spotlighted/playable がなくてもデフォルト False で読み込める。"""
    # favorite/spotlighted/playable キーが存在しない旧形式データ
    data = {
        "name": "Aldric", "age": 25, "gender": "male",
        "race": "Human", "job": "Warrior",
        "location": "Aethoria Capital",  # 旧形式: location フィールド
    }
    char = Character.from_dict(data)
    assert char.favorite is False
    assert char.spotlighted is False
    assert char.playable is False
```

### 10.4 イベント密度 / 通知密度テスト（PR-5 必須）

```python
def test_simulation_generates_events_without_notifications():
    """内部イベントが生成されても、通知閾値を超えなければ月報に掲載されない。"""
    # notification threshold を高く設定
    # 月次進行で内部イベントは記録されるが、月報は空
    ...


def test_notification_fires_on_dying_spotlight():
    """spotlighted キャラが dying になったとき通知が発生する。"""
    ...
```

### 10.5 決定論テスト（Phase 1 完了後必須）

```python
def test_seed_fixed_world_generation_is_deterministic():
    """同じ seed で世界生成すると同じ結果になる。"""
    world1 = _build_default_world(seed=42)
    world2 = _build_default_world(seed=42)
    assert world1.to_dict() == world2.to_dict()


def test_seed_fixed_12_months_is_deterministic():
    """同じ seed で 12 ヶ月進行すると同じスナップショットになる。"""
    sim1 = Simulator(seed=42)
    sim2 = Simulator(seed=42)
    for _ in range(12):
        sim1.step()
        sim2.step()
    assert sim1.to_dict() == sim2.to_dict()
```

---

## 11. フェーズ要約

| Phase | PR | 主な成果物 | Safety Invariant | 状態 |
|---|---|---|---|---|
| Phase 0 | PR-0 | 設計書但し書き | — | 未着手 |
| Phase 1a | PR-1, PR-2 | パッケージ整備・migration 基盤 | 未確立（旧コード） | ✅ PR-2 完了（PR #11） |
| Phase 1b | PR-2.5 | Favorite/Spotlight/Playable | 未確立 | 未着手 |
| Phase 1c | PR-3 | LocationState・location_id 一括移行（旧参照ゼロ） | **SI-1〜SI-3 確立** | 🔶 部分完了（PR #11） |
| Phase 2 | PR-4〜6 | 月報・Rumor・自動進行 | SI 維持 |
| Phase 3 | PR-7〜8 | Relationship・dying | SI 維持 |
| Phase 4 | PR-9〜11 | パーティ冒険・AA マップ | SI 維持 |
| Phase 5 | 未定 | Vow/secrecy 体系化 | SI 維持 |

---

## 12. 不変条件の完全リスト

本計画書で追加・確認した不変条件を設計書 §15.5 に加えて以下に列挙する。

| ID | 不変条件 | 確立 PR | 状態 |
|---|---|---|---|
| SI-1 | `character.location_id` は有効な `LocationState.id` を参照する | PR-3 | 🔶 location_id 導入済、LocationState 未完 |
| SI-2 | `world.get_location_by_id(character.location_id)` は None を返さない | PR-3 | 🔶 location_id 導入済、LocationState 未完 |
| SI-3 | `WorldEventRecord.location_id` は有効 id または None | PR-3 | ✅ WorldEventRecord 導入済（PR #11） |
| SI-4 | `schema_version` はすべての save データに存在する | PR-2 | ✅ 完了（PR #11） |
| SI-5 | `dead` キャラは active adventure の member でない | PR-8 |
| SI-6 | `retired` キャラは frontline quest を持たない | PR-8 |
| SI-7 | `rumor.reliability` は `{"certain","plausible","doubtful","false"}` の値のみ | PR-5 |
| SI-8 | `memorial.subject_ids` の全 id は存在するキャラを参照する | PR-10 |
| SI-9 | `month` は 1 以上の正整数 | PR-3 |
| SI-10 | 状態量（prosperity 等）は 0〜100 の範囲 | PR-3 |
| SI-11 | `dying` キャラは `alive=True` を維持する | PR-8 |
| SI-12 | active adventure の `member_ids` は全員 `alive=True` | PR-8 |

---

## 13. 開発開始判断（2026年3月時点）

### 13.1 スタート条件

以下がすべて満たされた時点で Phase 1a（PR-1）の開発を開始できる。

- [x] 本計画書（`docs/implementation_plan.md`）が main ブランチにマージされている
- [x] `docs/next_version_plan.md` が参照可能である
- [ ] PR-0（設計書但し書き）をマージするか、スキップの合意がある
- [ ] `requirements-dev.txt` の内容（pytest, hypothesis のバージョン）の合意がある

### 13.2 最初に着手すべき PR

**PR-2 → PR-2.5 → PR-3 の順が最優先。**

PR-1（パッケージ構造化）はロジック変更がなく安全だが、構造化が完了するまで PR-3 を待つ必要は**ない**。  
PR-3 の location 参照一括修正が最も技術的負債を解消するため、チームのリソースが許す限り PR-3 を早期にマージすることを推奨する。

### 13.3 リスク項目

| リスク | 対策 |
|---|---|
| PR-3 が大規模になり review コストが高い | §6.3 の置換順序で細分化し、差分を読みやすくする |
| 旧セーブの location 名に typo や独自名が含まれる | `loc_` + slug フォールバックで対応。load 時に警告ログを出す |
| PR-3 後に `character.location` への参照が残存する | PR-3 マージ前に `character\.location\b` grep を CI で実行する |
| テストの決定論性が崩れる | PR-3 で seed 固定テストを追加し、CI で必ず実行する |

---

*以上をもって、本書を Fantasy Simulator vNext の公式実装計画書とする。*
