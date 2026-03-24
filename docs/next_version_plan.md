# Fantasy Simulator vNext 改訂設計書（詳細レビュー反映・完全版）

**プロジェクト名**: Fantasy Simulator
**世界名**: Aethoria（エイソリア）
**版**: Review-Integrated Draft 4
**最終更新**: 2026-03-23
**位置づけ**: 詳細レビューの P0 / P1 指摘を反映し、実装移行・UIモック・具体例まで含めて再構成した vNext 基礎設計書

> **注意**: 実装順・PR 分割・完了条件・現状認識の正本は `docs/implementation_plan.md` に従ってください。本書は中長期の設計目標を定義する文書です。正式な migration chain・ID 規則・location 参照修正方針も `docs/implementation_plan.md` を優先し、本書の §15 migration 例は設計上の参考例として扱います。
> 現在の main では、月次進行基盤、world memory、terrain/site/route 分離、atlas 観測 UI 初版、
> schema v7 migration まで実装済みです。本書の As-Is は「この設計書が解決を意図した歴史的な弱点」として読んでください。

---

## 0. 本文書の目的

本書は、**vNext の設計を実装可能な水準まで具体化する**ことを目的とする。

本書は次の4つを同時に満たす。

1. **設計思想の明確化**
   何を目指すゲームか、何を中核体験とするかを定義する。

2. **現行コードからの移行経路の明示**
   既存クラス・保存形式・UI・テストをどう壊さずに更新するかを示す。

3. **プレイヤー体験の具体化**
   月報・年報・噂・AA風マップ表示など、プレイヤーが実際に目にするものをモック込みで定義する。

4. **レビュー指摘への直接回答**
   P0 / P1 論点に対して、仕様・数値・責務・実装順を明記する。

---

## 1. vNext の中心体験と最上位原則

### 1.1 中心体験

本作の中心体験は次の一文で定義する。

**自律的に生きる冒険者たちの世界を観察し、噂を読み、痕跡を追い、必要なときだけ介入し、ときにその一人へズームインして生きる群像ファンタジー・シミュレーション。**

### 1.2 最上位原則

1. **世界はイベントの背景ではなく状態機械である**
2. **人物は能力値の束ではなく物語状態を持つ**
3. **観察は鑑賞ではなく判断を伴うゲームプレイである**
4. **フレーバーテキストは主機能だが、編集規則を持つ**
5. **魅力的な機能でも、スキーマ・migration・テスト不能なら正式採用しない**

### 1.3 今回の改訂で解決対象とする現行の弱点

* `Location` が静的で、世界状態を持たない
* `event_log: List[str]` が構造化データを持たない
* `relationships: Dict[str, int]` により人間関係が一次元数値に還元されている
* 死が即時確定しやすく、dying 段階がない
* 冒険がソロ前提で、能力値や方針が結果に十分効かない
* 観察結果がログ羅列になりやすく、月報・年報・復帰サマリーがない
* マップが座標表示に寄り、土地の状態と歴史が読みにくい
* 保存形式に `schema_version` がなく、migration 前提になっていない

---

## 2. レビュー対応トレーサビリティ表

| レビュー論点                    | 本書の対応章        |
| ------------------------- | ------------- |
| Location が静的で状態がない        | §5            |
| 定性ラベルと数値の二重管理が危険          | §5.2, §5.3    |
| 伝搬規則が自然言語のまま              | §5.5          |
| event_log が文字列のみ          | §5.8          |
| relationships が一次元数値のみ    | §7            |
| Vow 遷移のトリガーが曖昧            | §7.4          |
| secrecy を早く入れすぎ           | §7.3.2        |
| dying 段階がない               | §8            |
| AdventureRun がソロ前提        | §9            |
| 冒険結果に能力値が効かない             | §9.6          |
| 冒険方針の選択主体が未定義             | §9.3          |
| 観察がゲームプレイになっていない          | §10, §11, §13 |
| 月報/年報の具体例不足               | §10.2         |
| reliability の `false` が曖昧 | §11.3         |
| 4層テンプレートの具体例不足            | §14.3         |
| エントリポイント配置が未定義            | §16.2         |
| 不変条件が少ない                  | §15.4         |
| EventResult.year 互換が未定義   | §15.3         |
| Phase 1 で状態可視化が弱い         | §18.1         |

---

## 3. As-Is と To-Be

### 3.1 As-Is（現行）

* 月次内部進行を持つ CLI シミュレーター
* 6属性・種族・職業・関係タグ基盤・パーティ冒険・保留選択
* event records / 月報 / 年報 / world memory を伴う観察体験
* terrain/site/route と atlas overview を含む観測 UI 基盤
* RNG 注入による再現性と schema-versioned JSON 保存

### 3.2 To-Be（vNext）

* 内部月次進行
* 世界状態・地域状態・噂・依頼・評判の正式化
* パーティ冒険
* dying を含む死の段階化
* 観察用月報 / 年報 / 復帰サマリー
* 情報の確度レイヤー
* AA風を含む文字ベースの濃い観測UI
* ✅ schema_version と migration chain（PR #11 にて実装済）

---

## 4. 時間モデル

### 4.1 基本方針

内部時間単位は**月**とする。
ただし、プレイヤー体験は毎月入力を要求せず、**条件付き自動進行**を標準とする。

### 4.2 月次進行フロー

```text
月開始
  1. 前月持越し状態に対する伝搬
  2. 季節補正
  3. 依頼生成
  4. 噂生成・伝播
  5. NPC 冒険者行動決定
  6. パーティ/冒険進行
  7. dying / rescue / retreat 解決
  8. scene 候補抽出
  9. 当月結果に対する再伝搬
 10. 月報生成
月終了
```

### 4.2.1 ステップ9の再伝搬対象

当月結果に対する再伝搬は、**即時性の高い状態量に限定**する。

* 再伝搬する: `danger`, `mood`
* 再伝搬しない: `traffic`, `prosperity`, `rumor_heat`

理由:

* `danger` と `mood` は戦闘、災害、喪失、成功帰還の影響をその月のうちに周辺へ波及させる必要がある
* `traffic`, `prosperity`, `rumor_heat` は遅効性が強く、次月の通常更新で十分である

これにより、当月中に発生した大事件の余波は即座に出しつつ、伝搬の過剰連鎖を防ぐ。

### 4.3 年の役割

年はUI上残す。用途:

* 年齢加算
* 年報生成
* 引退判定
* 世代ゴール判定
* 世界史イベントの節目管理

### 4.4 条件付き自動進行

```text
次のいずれかまで自動進行
- 自作冒険者に重大イベント
- 注目対象が serious / dying
- 保留選択発生
- 注目パーティ帰還 or 壊滅
- 新依頼カテゴリ出現
- 3 / 6 / 12ヶ月経過
```

### 4.5 自動進行停止条件の優先度

複数停止条件が同月に発火した場合に備え、優先度を持たせる。

```python
AUTO_PAUSE_PRIORITIES = {
    "dying_spotlighted": 100,
    "pending_decision": 90,
    "party_returned": 70,
    "new_quest_category": 50,
    "months_elapsed": 10,
}
```

最も高い優先度の条件を「停止理由」として表示し、他条件は補足として畳む。

### 4.6 テンポ目標値

* 最頻値: 5〜8ヶ月
* 中央値: 8〜12ヶ月
* 1ヶ月停止の連続は稀
* 24ヶ月以上ノーイベント停止は原則避ける

この分布は seed 固定テストシムで計測する。

---

## 5. ワールドモデル

### 5.1 目的

`Location` を「名前付きセル」から、「状態と記憶を持つ場所」へ引き上げる。

### 5.1.1 基礎世界設定は runtime state から分離する

現行 main では `content/world_data.py` が `WORLD_LORE`, race, job, default location を一体で抱えているが、
これは「Aethoria の暫定 seed data」がそのまま実装正本になっている状態である。
基礎世界設定が未確定である以上、vNext では **世界設定そのものを後から差し替え・追加できる** ことを前提にする。

したがって、`World` の runtime state と、世界観・初期定義・命名規則を持つ静的 bundle を分離する。

```python
@dataclass
class WorldDefinition:
    world_key: str
    display_name: str
    lore_blocks: list[str]
    races: list["RaceDef"]
    jobs: list["JobDef"]
    default_sites: list["SiteSeed"]
    naming_rules: dict[str, str]
```

最低限の方針は次とする。

- `World` は年、地形、event_records、memory、characters などの runtime state を持つ
- `WorldDefinition` は lore / race / job / location seed / naming などの静的定義を持つ
- デフォルトの Aethoria は同梱の 1 bundle として扱い、唯一の正史ハードコードとはみなさない
- 保存データは `world_definition_key` を持ち、対応 bundle が無い場合の fallback を定義する
- Phase 1 では stdlib のみで扱いやすい **JSON** を正本候補とし、YAML 等は後段の選択肢とする

### 5.1.2 世界観設定整理の authoring パートを明示的に持つ

設定 bundle の loader だけでは、世界観は自動では整理されない。
現状の課題は「Aethoria の seed data がある」ことではなく、
**何が確定設定で、何が未確定で、何を生成系へ委ねるかが未整理** なまま simulation を始めていることにある。

そのため vNext では、実装 Phase とは別に、少なくとも 1 本は
**世界観設定整理と初期 bundle authoring のための作業パート** を持つ。

最低限ここで整理するもの:

- world concept
- era / historical spine
- race / job の立ち位置
- race ごとの lifespan / homeland / culture / naming / inter-group relation
- geography / culture / naming rule
- glossary / taboo / symbolic vocabulary
- default site seed と region role

### 5.1.3 類例に近い歴史的世界変化を扱えるようにする

本作が目指す方向は、少なくとも次の既存ゲーム要素と親和性が高い。

- `Dwarf Fortress`: site の陥落、文明の興亡、地名や歴史的意味の蓄積
- `Crusader Kings` 系: 戦争、支配交代、文化・時代の推移
- `Caves of Qud`: 歴史層、固有名、地名や遺物の語り直し

したがって vNext では、次の 5 系統を正式に扱える設計へ寄せる。

1. war / occupation
2. official renaming / aliases
3. terrain mutation / route mutation
4. era transition
5. civilization drift

これらは event の description ではなく、world state として保持する。

### 5.2 LocationState — 🔶 基盤実装済、状態量は未導入

> **実装状況**: PR #11 にて `Location` に `id` フィールドを追加し、`location_id` ベースの参照に移行済。`LocationState` への完全移行（prosperity, safety, mood 等の状態量追加）は今後の PR で対応。

内部状態量と表示ラベルを分離し、**内部では原則数値を持つ**。

```python
@dataclass
class LocationState:
    id: str
    canonical_name: str
    region_type: str
    x: int
    y: int
    prosperity: int          # 0-100
    safety: int              # 0-100
    mood: int                # 0-100
    danger: int              # 0-100
    traffic: int             # 0-100
    visited: bool
    controlling_faction_id: str | None
    rumor_heat: int          # 0-100
    road_condition: int      # 0-100
    recent_event_ids: list[str]
    aliases: list["LocationAlias"]
    memorial_ids: list[str]
```

### 5.3 表示用ラベルへの導出

```python
PROSPERITY_LABELS = [
    (0, 20, "ruined"),
    (20, 45, "declining"),
    (45, 75, "stable"),
    (75, 101, "thriving"),
]

SAFETY_LABELS = [
    (0, 20, "lawless"),
    (20, 45, "dangerous"),
    (45, 75, "tense"),
    (75, 101, "peaceful"),
]

MOOD_LABELS = [
    (0, 20, "grieving"),
    (20, 45, "anxious"),
    (45, 75, "calm"),
    (75, 101, "festive"),
]
```

この方式により、「danger が高いのに safety_label が peaceful」のような不整合を内部で作らない。
UI・ログ・AA描画では、必ず数値から導出したラベルを使う。

### 5.4 各状態量の意味

* `prosperity`: 経済活動・商流・街の活気
* `safety`: 治安・秩序・公的保護の強さ
* `mood`: 共同体感情・空気
* `danger`: 探索・通行・遠征の直接危険度
* `traffic`: 人流・物流・冒険者流入
* `rumor_heat`: 噂と注目の集中度
* `road_condition`: 経路の通りやすさ

### 5.5 状態量が効く先

* 依頼発生率
* 噂の熱量
* 遠征危険度
* NPC 流入
* 交易イベント
* マップ描画差分
* 月報 / 年報要約

### 5.6 地域状態の伝搬規則

レビュー対応として、伝搬を自然言語ではなく数値テーブルで定義する。

```python
PROPAGATION_RULES = {
    "danger": {
        "decay": 0.30,
        "cap": 15,
        "min_source": 40,
    },
    "traffic": {
        "decay": 0.20,
        "cap": 10,
        "min_source": 35,
    },
    "mood_from_ruin": {
        "source_threshold": 20,
        "neighbor_penalty": 5,
        "max_neighbors": 4,
    },
    "road_damage_from_danger": {
        "danger_threshold": 70,
        "road_penalty": 8,
    },
}
```

#### 伝搬の意味

* 高い `danger` は隣接地へ漸減伝搬する
* 高い `traffic` は隣接地へ活気を押し出す
* 荒廃地は隣接地の `mood` を悪化させる
* 極端な `danger` は周辺 `road_condition` を悪化させる

### 5.7 季節補正マトリクス

```python
SEASONAL_MODIFIERS = {
    ("winter", "mountain"): {"danger": +30, "road_condition": -20},
    ("winter", "trade_road"): {"traffic": -20},
    ("spring", "settlement"): {"quest_spawn": +15},
    ("summer", "port"): {"traffic": +20},
    ("autumn", "lawless_road"): {"danger": +10},
}
```

### 5.8 グリッドサイズ方針

初期実装は 5×5 を維持してよいが、構造としてサイズ固定前提にしない。

* `WORLD_WIDTH`, `WORLD_HEIGHT` を設定化
* map renderer は可変サイズ前提
* 近傍計算はユーティリティ関数へ集約

### 5.9 構造化イベント記録 ✅ 基盤実装済（PR #11）

> **実装状況**: `WorldEventRecord` の基本版が PR #11 で導入済。フィールド構成は設計書と一部異なる（`record_id`, `kind`, `year`, `severity`, `visibility` 等）。`month` への移行と `tags`/`summary_key` の追加は Phase 2 以降の対応。

```python
@dataclass
class WorldEventRecord:
    id: str
    month: int
    category: str
    actor_ids: list[str]
    location_id: str | None
    tags: list[str]
    summary_key: str
```

`event_log: List[str]` は人間向け派生物として残すが、ゲーム内部の因果は `WorldEventRecord` を参照する。現行実装では互換のため `Simulator.history: List[EventResult]` も残っているため、Phase 2 までは「`WorldEventRecord` が正規ストア、`history` / `event_log` は adapter / 派生物」という扱いに統一する。

### 5.9.1 UI 連携規約

- `WorldEventRecord` は保存・通知判定・因果追跡に用いる正規イベント表現とする。
- UI / report 層が `EventRecord` などの表示用レコードを持つ場合、それは `WorldEventRecord` から導出する非永続の view model に限る。
- Phase 1〜2 の互換期間は、`Simulator.history` と `event_log: List[str]` を adapter / 派生物として扱い、正規データ源は `WorldEventRecord` に一本化する。

---

## 6. 土地の歴史と痕跡

### 6.1 通称

```python
@dataclass
class LocationAlias:
    alias_name: str
    start_month: int
    cause_tag: str
    source_event_id: str
```

### 6.2 記念碑・墓碑

```python
@dataclass
class Memorial:
    id: str
    location_id: str
    type: str  # grave / monument / battle_site / ruin_marker
    title: str
    subject_ids: list[str]
    created_month: int
    narrative_key: str
```

### 6.3 live trace

* 先行パーティが攻略済みで報酬減少
* 最近通過したパーティにより一時的に `safety` 上昇
* 失敗遠征隊のため `danger` 上昇
* 冒険者流入により `traffic` と `mood` が変動

### 6.4 live trace の導入時期

`Quest` と `WorldEventRecord` が必要なため、live trace 本体は Phase 4 導入とする。
ただし、それを支える記録構造は Phase 1 で入れる。

---

## 7. キャラクターモデル

### 7.1 Character コア

```python
@dataclass
class Character:
    id: str
    name: str
    age: int
    gender: str
    race: str
    alive: bool
    location_id: str
    custom_created: bool = False
    favorite: bool = False
    spotlighted: bool = False
    playable: bool = False
```

### 7.2 CharacterAbilities

```python
@dataclass
class CharacterAbilities:
    character_id: str
    strength: int
    intelligence: int
    dexterity: int
    wisdom: int
    charisma: int
    constitution: int
    level: int
    xp: int
```

### 7.3 CharacterNarrativeState

```python
@dataclass
class CharacterNarrativeState:
    character_id: str
    scars: list[str]
    vows: list["Vow"]
    losses: list[str]
    unresolved_promises: list[str]
    grudges: list[str]
    titles: list[str]
    defining_memories: list[str]
```

### 7.4 Relationship

```python
@dataclass
class Relationship:
    target_id: str
    affinity: int
    relation_tags: list[str]
    source_event_ids: list[str]
    last_major_update_month: int
```

#### relation_tags 例

* friend
* rival
* spouse
* lover
* mentor
* disciple
* debtor
* savior
* betrayer
* family
* former_friend

### 7.5 `secrecy` の扱い

`secrecy` は面白いが、Rumor / Reputation / 暴露イベントと同時設計しないと死にフィールドになりやすい。
したがって、**Phase 3 では導入せず、Phase 5 で rumor/reputation 拡張と同時に再評価する。**

### 7.6 Vow

```python
@dataclass
class Vow:
    id: str
    subject_id: str
    target_id: str | None
    vow_type: str
    state: str  # active / tested / strained / fulfilled / broken / abandoned
    created_month: int
    tested_count: int
    strain_level: int
```

### 7.7 Vow 遷移のトリガー仕様

#### active → tested

* vow に反する選択肢または状況が発生した
* 対象人物 / 対象地点 / 対象派閥が高危険状態に入った
* Quest / retreat 判断が vow と衝突した

#### tested → strained

* `tested_count >= 2`
* tested 状態のまま再び vow に反する圧力を受けた
* `strain_level` が追加された

#### strained → broken

* `strain_level >= 3`
* vow に反する行動を実際に選んだ、または AI が選んだ

#### active / tested / strained → fulfilled

* 対象救出、宿敵討伐、目的地到達、約束履行などの達成条件を満たした

#### active / tested / strained → abandoned

* 対象消滅・死亡・無効化により誓いが意味を失った
* 引退や人格変化により意図的に誓いを捨てた

### 7.8 EventSystem との接続

Vow チェックを優先するイベント系統:

* quest_accept / quest_reject
* retreat / rescue
* reunion / betrayal
* death / disappearance
* faction_conflict
* protect / avenge / abstain 系の scene_event

### 7.9 VOW_FULFILLMENT_CONDITIONS の扱い

`fulfilled` 条件の type 別詳細表は Phase 5 で正式化する。
ただし、設計上は以下のスケルトンを前提とする。

```python
VOW_FULFILLMENT_CONDITIONS = {
    "protect": ["target_survived", "target_escaped", "danger_resolved"],
    "avenge": ["rival_defeated", "culprit_exposed", "blood_debt_paid"],
    "find": ["target_found", "place_reached", "artifact_recovered"],
    "abstain": ["temptation_refused", "period_endured", "taboo_maintained"],
}
```

Phase 3〜4 では、fulfilled 判定は個別イベント側のフラグで簡易対応し、Phase 5 で `vow_type` ごとの共通判定へ引き上げる。

### 7.9 ReputationEntry

```python
@dataclass
class ReputationEntry:
    subject_id: str
    impression_tag: str
    intensity: int
    source_type: str  # direct / rumor / public_record
    certainty: str
```

### 7.10 分割タイミングの裁定

* Phase 1〜2: `Character` の保存形式は原則フラット互換を維持
* Phase 3: `Relationship` 構造化と同時に、`CharacterAbilities` / `CharacterNarrativeState` の分離を進める

これにより、移行コストを一度に爆発させない。

---

## 8. 死の段階化と救助

### 8.1 状態遷移

```text
healthy → injured → serious → dying → dead
```

### 8.2 dying の役割

* 自作冒険者: 原則通知
* favorite / spotlighted: 高優先通知
* 主人公モード中: scene 化優先
* 非注目 NPC: 要約解決可

### 8.3 最後の一手

`dying` 中は次を評価する。

* 救助能力
* 撤退判断
* 所持資源
* 回復拠点距離
* 地点 danger
* プレイヤー介入有無

### 8.4 引退と消息不明

```python
retirement_state: active / resting / retired / settled
missing_state: none / missing_recent / missing_long / presumed_dead
```

### 8.5 eligible フィルタの更新

`retired` だが `alive=True` のキャラが frontline 系イベントに混ざらないよう、イベント参加 eligible 条件に `retirement_state == active` を加える。

---

## 9. 冒険システム

### 9.1 AdventureRun

```python
@dataclass
class AdventureRun:
    id: str
    party_id: str | None
    member_ids: list[str]
    objective_type: str
    target_location_id: str
    policy: str
    retreat_rule: str
    supply_state: str
    danger_level: int
    scene_queue: list[str]
    return_state: str
```

### 9.2 方針一覧

* 慎重探索
* 最短踏破
* 金策重視
* 救助優先
* 遺物回収重視
* 殲滅志向
* 痕跡隠蔽
* 裏工作重視

### 9.3 方針選択の主体

* `spotlighted` / `playable` キャラ: **プレイヤーが選択**
* `favorite` キャラ: **プレイヤーが推奨方針を出し、AI が最終決定**
* その他 NPC / 非注目パーティ: **AI が性向・関係・資源状況から決定**

### 9.4 AI 方針決定の基本入力

* caution
* ambition
* loyalty
* greed
* current injuries
* supply_state
* target_location danger
* vow / grudge / relationship pressure

### 9.5 撤退基準

* 誰かが serious 以上
* 食料不足
* 呪い蓄積
* 希少品確保
* ボス遭遇
* 注目対象が dying

### 9.6 冒険結果に能力値を効かせる

* STR / CON → 正面戦闘・耐久
* DEX / WIS → 罠回避・撤退判断
* INT / Mystic skill → 禁忌・遺跡・儀式対応
* caution → retreat threshold
* ambition → 続行寄り判断
* loyalty → 負傷仲間を置き去りにしにくい

### 9.7 生死判定の改善

純粋な `roll < 0.24 で即死` のような処理は採用しない。
`injured / serious / dying` を経由させ、dying 段階で救助・撤退・介入を評価する。

### 9.8 方針選択 UI モック

```text
遠征方針を決める ─ Black Hounds / Shadowcrypt
=============================================
  対象: Shadowcrypt
  危険: 高
  噂: cursed / sealed (doubtful)
  現在補給: 中

  [1] 慎重探索
  [2] 最短踏破
  [3] 金策重視
  [4] 救助優先
  [5] 遺物回収重視
  [6] 殲滅志向
  [7] 痕跡隠蔽
  [8] 裏工作重視

  撤退基準:
  [A] 誰かが serious 以上で撤退
  [B] 食料不足で撤退
  [C] 希少品確保で帰還
  [D] ボス発見で一旦撤退
```

### 9.9 冒険結果の世界反映

* quest 更新
* rumor 生成
* location danger / safety / mood 更新
* memorial 生成
* reputation 更新
* live trace 更新

---

## 10. 観察体験

### 10.1 月報

対象:

* 自作冒険者
* favorite
* spotlighted
* 注目パーティ

内容:

* 何をしたか
* どこへ行ったか
* 何を得た / 失ったか
* 状態悪化や転機

### 10.2 月報モック

```text
═══════════════════════════════════════
  Aethoria 月報 ─ 1003年 冬の第2月
═══════════════════════════════════════

  ▶ あなたの冒険者たち
    Aldric [健康]  Silvermere にて訓練中
    Lysara [負傷]  Elderwood より帰還。古代の遺物を持ち帰った

  ▶ 注目人物
    Grimjaw [dying] Shadowcrypt 深部で重傷。救助隊が向かっている
    → 介入しますか？ [はい / いいえ]

  ▶ 噂
    「東の山脈でドラゴンの目撃情報」 (plausible)
    「Ironhold の鍛冶組合が新武器を完成させたらしい」 (doubtful)

  ▶ 依頼板の動き
    [完了] Goblin Hunt (Black Hounds) @ Silvermere
    [失敗] 遺跡調査 (Dawn Spears / 消息不明) @ Shadowcrypt
    [新規] 護衛依頼: Golden Meadow → Ironhold (urgency: high)

  ▶ 世界の動き
    Silvermere の交易量が3ヶ月連続で減少
    Frostpeak 街道が雪で封鎖
═══════════════════════════════════════
```

### 10.3 年報

内容:

* 主要都市の状態変化
* 有名冒険者の消息
* 記念碑化された事件
* 地名変化
* 世界圧力の進行
* あなたの冒険者たちの一年

### 10.4 年報モック

```text
═══════════════════════════════════════
  Aethoria 年報 ─ 1003年
═══════════════════════════════════════

  ▶ 世界の要点
    - Silvermere は declining へ転落、交易量が大きく低下
    - Frostpeak 街道は冬季封鎖が長引き、北方依頼が滞留
    - Shadowcrypt 周辺の danger が上昇し、救助依頼が増加

  ▶ 名の残った出来事
    - Black Hounds が Goblin Hunt を完了
    - Dawn Spears は遺跡調査中に消息を絶つ
    - Elderwood 南端に「槍折れの塚」が建立される

  ▶ あなたの冒険者たちの一年
    - Aldric は生存。剣技を伸ばし、護衛依頼で名を上げた
    - Lysara は大怪我から復帰し、古代遺物の持ち帰りで注目を集めた
═══════════════════════════════════════
```

### 10.5 復帰サマリー

主人公モードから離れていたキャラに戻る際、AI 委任期間の行動を提示する。

### 10.6 目撃報酬

注目していた対象の重大イベントは、後からまとめて読むより高密度な描写を得る。

### 10.7 学習ポイント設計

#### 学習ポイント #1: 冬の山越えは危険

* 根拠メカニクス: `season=winter && region_type=mountain -> danger_modifier = +30`
* 発見方法: 冬の山岳遠征で負傷・撤退が増える
* 期待発見時期: 2〜3年目

#### 学習ポイント #2: ambitious は深追いしやすい

* 根拠メカニクス: `ambition` が高いほど retreat threshold が下がる
* 発見方法: cautious な仲間より撤退が遅い
* 期待発見時期: 3〜5年目

#### 学習ポイント #3: doubtful な噂は空振りしやすい

* 根拠メカニクス: `doubtful` は情報欠損と false 混入率が高い
* 発見方法: 噂追跡依頼が空振り・誤情報に繋がる
* 期待発見時期: 4〜8年目

#### 学習ポイント #4: 治安悪化した街では依頼の質が変わる

* 根拠メカニクス: `safety` 低下で討伐・護衛・闇取引系依頼の重み上昇
* 発見方法: 同じ街でも数年後に依頼板の傾向が変わる
* 期待発見時期: 5〜10年目

#### 学習ポイント #5: 引退者は世界に残る

* 根拠メカニクス: 引退者が酒場主・教官・依頼発注者へ遷移しうる
* 発見方法: かつての注目冒険者が別役割で再登場する
* 期待発見時期: 8〜15年目

---

## 11. 依頼・噂・情報確度

### 11.1 Quest

```python
@dataclass
class Quest:
    id: str
    category: str
    issuer_id_or_faction: str
    origin_location_id: str
    target_location_id: str
    urgency: str
    reward_band: str
    danger_band: str
    status: str  # open / claimed / completed / failed / expired
    world_effects: list[str]
```

### 11.2 Rumor

```python
@dataclass
class Rumor:
    id: str
    category: str
    source_location_id: str
    target_subject_or_location: str
    reliability: str  # certain / plausible / doubtful / false
    spread_level: int
    age_in_months: int
    content_tags: list[str]
```

### 11.3 reliability と DISCLOSURE

```python
DISCLOSURE = {
    "certain":   {"who": 1.0, "what": 1.0, "where": 1.0, "when": 1.0},
    "plausible": {"who": 0.9, "what": 0.8, "where": 0.7, "when": 0.5},
    "doubtful":  {"who": 0.5, "what": 0.6, "where": 0.3, "when": 0.2},
    "false":     {"who": 0.3, "what": 0.0, "where": 0.5, "when": 0.1},
}
```

### 11.4 `false` の意味

`false` で `"what": 0.0` なのは、「what が単に省略される」のではなく、**誤った内容へ置換される可能性がある**ことを意味する。
つまり `false` は「欠損」ではなく、**情報欠損 + 誤情報混入**である。

### 11.5 語り部

語り部は Rumor システムの特殊形であり、未観測の出来事を再叙述する。
ただし、序盤は信頼度を高めに設定し、プレイヤーが情報確度の概念に慣れてから揺らぎを増やす。

### 11.6 依頼板の痕跡表示

* 完了済み依頼
* 失敗した依頼
* 消えた依頼
* 他パーティが達成した依頼

### 11.7 依頼板モック

```text
Silvermere 依頼板
═══════════════════════════════════════
  [完了] ゴブリン討伐 (Black Hounds 達成) ──── 報酬済み
  [失敗] 遺跡調査 (Dawn Spears / 消息不明) ── ×
  [期限切れ] 護衛依頼: 該当なし
  ─────────────────────────────────────
  [募集中] 街道パトロール     urgency: ●○○  danger: ●●○  報酬: 中
  [募集中] 薬草採取           urgency: ●●○  danger: ●○○  報酬: 低
  [募集中] 古代遺跡探索       urgency: ○○○  danger: ●●●  報酬: 高
           └ 噂: cursed / sealed (doubtful)
═══════════════════════════════════════
```

---

## 12. シーン化と物語状態

### 12.1 転機タグ

* comeback
* reunion
* betrayal
* succession
* vow_test
* loss_chain
* unexpected_growth
* sacrifice

### 12.2 scene 化条件

* dying
* vow / grudge / family / rival に関する転機
* 主人公モード中の重大選択
* 喪失や継承の節目
* 利益相反の大きい局面

### 12.3 連打抑制

* 同一人物に短期連発しない
* 履歴に接続しない転機は優先度を下げる
* 外から重大でも本人に意味が薄ければ scene 優先度を下げる

### 12.4 EventSystem 接続方針

現行 `EventResult` に加え、scene 候補フラグまたは `SceneCandidate` 集約層を導入する。
Phase 2 時点では、`EventResult` に `scene_candidate: bool` を追加する軽量案を優先する。

---

## 13. マップ表示方針（AA モック付き）

### 13.1 基本方針

マップは単なる座標表示ではなく、**土地の状態・歴史・危険・交通・噂・事件痕跡を圧縮表示する観測UI**とする。

初期実装は文字ベースとし、三層構造を採用する。

1. **ワールド全体図**
2. **地域図**
3. **地点詳細図**

### 13.2 重要原則

* AA は装飾ではなく**内部状態の可視化**である
* UI が状態判定を持たないよう、`LocationState -> MapRenderInfo -> 描画` の変換層を設ける
* 可読性を最優先し、詳細 AA はズームイン表示に寄せる

### 13.3 MapRenderInfo

```python
@dataclass
class MapRenderInfo:
    base_glyph: str
    overlay_glyphs: list[str]
    label: str
    detail_template: str
    color_tags: list[str]
```

### 13.4 ワールド全体図モック

```text
                    ^^^^ Frostpeak
         /\      /\  .. seasonal pass
    /\  /  \____/  \       x recent losses
   /  \/            \__
   | F | Elderwood      \~~~~~~~ Serpent Sea
   | o |                 ~~~~~~~
   | r |      ==road==     [S]
   | e | Willowbrook ---- Silvermere ---- Ironhold
   | s |        |              |              |
   | t |        |           [*]碑             +-- ruined road
   \__/         |              |
             Golden Meadow   Aethoria Capital

凡例:
[S] 港町 / [*] 記念碑 / == 主要街道 / x 最近の死地 / .. 季節道
```

### 13.5 地域図モック

```text
Region: Silvermere Approaches（不安な空気 / 交易減少）

         x 先行パーティ全滅地点
        / \
  [Inn]==   ==[Gate]
      \   //     ! 噂熱高
       \_//
       [市壁]----[市場]
         |        |
         |      [掲示板]
         |         └ 完了: Goblin Hunt（Black Hounds）
         |
      [墓碑]

状態:
- prosperity_label: declining
- safety_label: tense
- mood_label: anxious
- traffic: 34
- danger: 58
```

### 13.6 地点詳細図モック（都市）

```text
Silvermere（不安な空気 / 交易低下）
========================================
      |\                     _[]_
   ___|_\_______     _______|_  |____
  |  _   _   _  |   |   market square |
  | |_| |_| |_| |   | [] []  []   []  |
  |             |   |                 |
  |  guild hall |---|   old well      |
  |______   ____|   |______   ________|
         | |                 | |
         | | 墓碑            | | 掲示板
         |_|_________________|_|

最近の痕跡:
- 先月、帰還しなかった探索隊がいた
- Black Hounds が討伐依頼を完了
- 港からの流入が止まり市場が沈んでいる
```

### 13.7 UI の段階的AA化

* Stage A: 記号中心 UI（世界全体図、依頼板、一覧）
* Stage B: 準 AA UI（地域図、掲示板、墓碑、注目カード）
* Stage C: 高密度 AA UI（地点詳細図、主人公モード場面、一部 scene_event）

### 13.8 実装制約

* モノスペース前提で崩れないこと
* 端末幅が狭い場合は簡易表示へフォールバックすること
* 色に依存せず文字だけでも意味が読めること
* AA と長文ログが競合しないこと

---

## 14. テキスト生成アーキテクチャ

### 14.1 方針

Phase 1〜4 は**決定論的なテンプレートベース**を基本とする。
LLM は必須前提にしない。

### 14.2 NarrativeContext

```python
@dataclass
class NarrativeContext:
    subject_ids: list[str]
    actor_roles: dict[str, str]
    event_tags: list[str]
    relation_tags: list[str]
    location_tags: list[str]
    season_tag: str
    tone_tag: str
    knowledge_scope: str
    certainty_level: str
    output_length: str
```

### 14.2.1 SettingBundle と NarrativeContext の接続

`NarrativeContext` は人物関係や最近イベントだけを見ればよいわけではない。
どの世界を舞台にしているか、どの文化圏・地理圏に属するかも文章選択に影響する。

そのため将来形では、最低限次を外部設定 bundle から参照できるようにする。

- world title / era name
- race / job の表示名と tone
- site type ごとの語彙差
- naming / epitaph / rumor に使う文化語彙
- 地域固有の用語や歴史タグ

```python
@dataclass
class NarrativeContext:
    world_definition_key: str
    region_culture: str | None
    faith_tag: str | None
    relation_tags: list[str]
    memory_tags: list[str]
```

こうすることで、Aethoria 専用の固定文面を増やすのではなく、
「後から差し込まれた世界設定 bundle の上で語れる叙述層」として拡張できる。

### 14.2.2 NarrativeContext だけでは世界観設定整理の代替にならない

`NarrativeContext` は「どう語るか」を決める層であり、
「そもそも何を世界設定として持つか」を整理する層ではない。

したがって実装計画上は、次の 2 段を分ける。

1. `WorldDefinition` / `SettingBundle` を導入し、叙述・UI・初期 world から参照できるようにする
2. その上で、最初の正式な setting bundle を整理・構築する

この分離により、シミュレーション基盤と設定 authoring を混同せずに進められる。

### 14.2.3 動的世界変化は NarrativeContext の外側で先に成立させる

戦争、改称、地形変化、時代交代、文明変化は、
まず world state と event record の層で成立していなければならない。
`NarrativeContext` はそれを語る層であって、変化そのものを作る層ではない。

したがって導入順は次とする。

1. world state に rename / faction / era / terrain mutation の受け皿を入れる
2. reports / atlas / region / detail に変化結果を出す
3. その後に `NarrativeContext` で「どう語るか」を強化する

### 14.3 生成階層

```text
Layer 1: 構造テンプレート
Layer 2: 語彙差し替えプール
Layer 3: 条件付き修飾子
Layer 4: 固有文オーバーライド
```

### 14.4 具体例: meeting

```python
MEETING_TEMPLATES = {
    "positive": "{modifier}{name1}と{name2}は{location_desc}で{encounter_verb}、{outcome}。",
    "neutral":  "{modifier}{name1}と{name2}は{location_desc}で{encounter_verb}。",
    "negative": "{modifier}{name1}と{name2}は{location_desc}で{encounter_verb}が、{outcome}。",
}

ENCOUNTER_VERBS = {
    "meeting": ["出会い", "顔を合わせ", "偶然すれ違い", "宿で隣り合わせになり"],
    "reunion": ["再会し", "久方ぶりに顔を合わせ", "思いがけず再び出会い"],
}

OUTCOME_POSITIVE = ["意気投合した", "深い信頼を築いた", "互いの技を認め合った"]
OUTCOME_NEGATIVE = ["険悪な空気に包まれた", "互いに距離を置いた", "言葉少なに別れた"]

def meeting_modifier(ctx: NarrativeContext) -> str:
    parts = []
    if ctx.season_tag == "winter":
        parts.append("雪の降りしきる")
    if "rival" in ctx.relation_tags:
        parts.append("因縁の")
    if ctx.certainty_level == "doubtful":
        parts.append("噂によれば、")
    return "".join(parts)

MEETING_OVERRIDES = {
    ("rival", "reunion", "winter"): "{name1}は雪の中、{name2}の背中を見つけた。二人の間に積もった年月が、白い息となって漂った。",
}
```

### 14.5 具体例: battle

```python
BATTLE_TEMPLATES = {
    "win":  "{modifier}{name1}は{location_desc}で{name2}を打ち破り、{outcome}。",
    "lose": "{modifier}{name1}は{location_desc}で{name2}に敗れ、{outcome}。",
}

BATTLE_VERBS = {
    "open": ["刃を交え", "激突し", "正面から衝突し"],
    "ambush": ["不意打ちを受け", "待ち伏せされ", "闇の中で襲われ"],
}

BATTLE_OUTCOMES_WIN = ["名声を得た", "相手の武名を奪った", "街に凱旋した"]
BATTLE_OUTCOMES_LOSE = ["傷を負って退いた", "名誉を失った", "命からがら逃れた"]
```

### 14.6 具体例: journey

```python
JOURNEY_TEMPLATES = {
    "safe":   "{modifier}{name1}は{from_loc}から{to_loc}へ向かい、{outcome}。",
    "hazard": "{modifier}{name1}は{from_loc}から{to_loc}への途上で{hazard}に見舞われた。",
}

JOURNEY_HAZARDS = {
    "winter_mountain": ["吹雪", "雪崩", "凍結した山道"],
    "lawless_road": ["追い剥ぎ", "待ち伏せ", "壊れた橋"],
}

JOURNEY_OUTCOMES = ["無事に到着した", "新たな噂を持ち帰った", "疲労しつつも目的地へ辿り着いた"]
```

### 14.7 接続方針

現行 `tr(key, **kwargs)` をすぐ廃止しない。
Phase 1〜4 では、`NarrativeContext` からテンプレートキーと修飾子を選ぶ `select_template()` を追加し、既存 i18n エンジンと併用する。

### 14.7.1 i18n 対応方針

4層テンプレートは Phase 2 からロケール対応する。
ただし Phase 1〜2 では、現行 `i18n.py` の `_TEXT` / `_TERMS` と `tr()` / `tr_term()` を source of truth とし、`select_template()` はロケール非依存のキー選択と修飾子決定を担当する。
Layer 1 の構造テンプレートと Layer 2 の語彙差し替えプールは、まず既存 i18n テーブルへ追加するか、互換 API を維持したローダー経由で供給する。
外部ファイル分離は `i18n.py` の互換契約を壊さない形で導入できる段階で行う。

これにより、文の骨格と語彙を言語ごとに切り替えつつ、イベント選択ロジックそのものは共有できる。

### 14.8 編集規則

* 重要点抽出
* 反復抑制
* 視点整合
* 既出表現の冷却期間
* 固有文優先
* surprise の温存

```python
COOLDOWN_RULES = {
    "same_template_key": 6,
    "same_verb_pool_item": 3,
    "same_override": 24,
}
```

### 14.8.1 冷却履歴の記憶先

テンプレート冷却の履歴は Phase 2 実装時に `narrative/context.py` 内の `TemplateHistory` として保持する。
役割は次の通り。

```python
@dataclass
class TemplateHistory:
    recently_used_template_keys: dict[str, int]
    recently_used_lexemes: dict[str, int]
    recently_used_overrides: dict[str, int]
```

この履歴はセーブ対象ではなく、月報・年報・scene 生成の短期反復抑制のための実行時キャッシュとして扱う。

---

## 15. 保存形式・schema・migration

> **⚠️ 実装時の注意**: 本章の migration 例（§15.3）は**概念例**です。正式な migration chain・location ID 規則・location 参照修正方針は `docs/implementation_plan.md` に従ってください。特に §15.3 の v1 に記載の `job → adventure_job` は**採用しない旧案**です。実装前に必ず `docs/implementation_plan.md` を参照してください。

### 15.1 schema_version

全 save データに `schema_version` を必須とする。

### 15.2 migration chain

```python
MIGRATIONS = {
    1: migrate_v0_to_v1,
    2: migrate_v1_to_v2,
    3: migrate_v2_to_v3,
    4: migrate_v3_to_v4,
}
```

### 15.3 移行例

* v1: schema_version 追加 + `job -> adventure_job`
* v2: `LocationState` 導入 + 月次時間導入
* v3: `Relationship` 構造化 + `ReputationEntry` 導入
* v4: injury 段階化 + dying 導入

### 15.3.1 `Location -> LocationState` の初期値テーブル

旧 `Location` から新 `LocationState` への移行では、最低限の初期値を次で与える。

```python
LOCATION_DEFAULTS = {
    "capital":  {"prosperity": 85, "safety": 80, "mood": 65, "danger": 15, "traffic": 90, "rumor_heat": 60, "road_condition": 85},
    "city":     {"prosperity": 70, "safety": 65, "mood": 55, "danger": 25, "traffic": 70, "rumor_heat": 45, "road_condition": 75},
    "village":  {"prosperity": 50, "safety": 55, "mood": 55, "danger": 30, "traffic": 35, "rumor_heat": 20, "road_condition": 55},
    "forest":   {"prosperity": 10, "safety": 30, "mood": 40, "danger": 55, "traffic": 15, "rumor_heat": 10, "road_condition": 35},
    "mountain": {"prosperity": 5,  "safety": 25, "mood": 35, "danger": 65, "traffic": 10, "rumor_heat": 10, "road_condition": 30},
    "dungeon":  {"prosperity": 0,  "safety": 10, "mood": 20, "danger": 80, "traffic": 5,  "rumor_heat": 35, "road_condition": 20},
    "plains":   {"prosperity": 35, "safety": 45, "mood": 50, "danger": 35, "traffic": 30, "rumor_heat": 15, "road_condition": 60},
    "sea":      {"prosperity": 0,  "safety": 20, "mood": 40, "danger": 60, "traffic": 25, "rumor_heat": 20, "road_condition": 0},
}
```

これにより、PR-3 で旧世界から新状態量へ無理なく移行できる。

### 15.4 EventResult の互換維持

月次化しても、初期移行では既存テストとの互換を保つため `EventResult.year` を残す。
同時に `EventResult.month` を追加し、`year` は `base_year + total_months // 12` から導出して設定する。

### 15.5 不変条件

* schema_version は必ず存在する
* dead は active adventure member ではない
* retired は frontline quest を持たない
* rumor.reliability は列挙型限定
* memorial.subject_ids は存在人物のみ
* すべての `character.location_id` は有効な `LocationState.id` を参照する
* month は 1 以上の正整数
* `prosperity / safety / mood / danger / traffic / rumor_heat / road_condition` は 0〜100 の範囲
* すべての `WorldEventRecord.location_id` は有効な `LocationState.id` を参照する（または None）
* すべての `WorldEventRecord.actor_ids` は有効な `Character.id` を参照する
* active adventure の `member_ids` は全員 alive である
* dying は alive=True を維持する

---

## 16. パッケージ構造とエントリポイント

### 16.1 新構造案

```text
fantasy_simulator/
  __main__.py
  core/
    character.py
    relationship.py
    reputation.py
    narrative_state.py
    location.py
    world.py
  mechanics/
    quest.py
    rumor.py
    adventure.py
    events.py
  narrative/
    context.py
    templates.py
    reports.py
    summary_rules.py
  persistence/
    schema.py
    migrations.py
    save_load.py
  ui/
    screens.py
    ui_helpers.py
    map_renderer.py
  i18n/
    engine.py
    ja.py
    en.py
```

### 16.2 エントリポイント方針

* 正式な実行経路は `python -m fantasy_simulator`
* ルートの `main.py` は互換維持の薄いラッパーとして残す

```python
# main.py (root)
from fantasy_simulator.__main__ import main

if __name__ == "__main__":
    main()
```

### 16.3 Character 分割のタイミング

* Phase 1〜2 は保存互換を優先し、Character の外形はなるべく維持
* Phase 3 で `Relationship` 構造化と同時に `CharacterAbilities` / `CharacterNarrativeState` 分離を進める

---

## 17. テスト戦略

### 17.1 単体テスト

* LocationState update
* propagation rules
* Relationship migration
* Reputation propagation
* Vow transition triggers
* dying / rescue logic
* AdventureRun state machine
* NarrativeContext validation
* MapRenderInfo 生成

### 17.2 統合テスト

* 月次進行数ヶ月
* 自動進行停止頻度
* quest / rumor / report 連動
* 主人公離脱 / 復帰

### 17.3 互換テスト

* 旧save読み込み
* migration chain
* 欠損補完
* EventResult.year 互換

### 17.4 決定論テスト

* seed 固定 world 生成
* seed 固定 12ヶ月進行
* スナップショット比較

### 17.5 property-based testing

Phase 1 では invariants の一部に限定採用する。

例:

* 死者が active party に残らない
* invalid reliability が生成されない
* month 進行後に location_id が不正値にならない

---

## 18. 実装フェーズ

### 18.1 Phase 1: 保存基盤と構造移行

**最初の PR 群は3つに絞る。**

PR-1:

* パッケージ構造化
* import パス移行
* `requirements-dev.txt` を追加（少なくとも `pytest`, `hypothesis` を含む）
* ロジック変更なし
* 全テスト通過

PR-2:

* schema_version 導入
* migrations.py 導入
* 旧save互換確保
* 全テスト通過

PR-3:

* `Location -> LocationState` 移行
* `WorldEventRecord` 導入
* `advance_time` の月次対応開始
* `render_map` に簡易状態表示を追加
* 全テスト通過

### 18.2 Phase 1 簡易マップ改善

AA 本体は Phase 4 でよいが、Phase 1 PR-3 の時点で「状態が見える」ことを優先する。
初期 `render_map` には少なくとも次を追加する。

* danger 数値
* safety_label（閾値導出）
* traffic の簡易指標
* 注目地点マーカー

### 18.3 Phase 2: 観察体験基盤

* 月報 / 年報 / 復帰サマリー
* 条件付き自動進行
* Rumor / reliability
* 注目対象通知

### 18.4 Phase 3: 人物と死の拡張

* Relationship 構造化
* ReputationEntry 導入
* dying / rescue
* 引退 / 消息不明

### 18.5 Phase 4: 冒険と世界痕跡

* AdventureRun のパーティ化
* 能力値依存 outcome
* live trace
* memorial / alias
* map renderer 初期 AA 版

### 18.6 Phase 5: 高解像度化

* scene 強化
* vow / grudge 体系化
* secrecy の再評価
* 語り部限定導入
* 地点詳細図の高密度 AA 化

---

## 19. 直近で作るべき成果物

1. `schema.py`
2. `migrations.py`
3. `LocationState` 定義
4. `WorldEventRecord` 定義
5. `Relationship` / `ReputationEntry` 定義
6. `NarrativeContext` 定義
7. `reports.py` の月報 / 年報仕様
8. `map_renderer.py` の `LocationState -> MapRenderInfo` 変換仕様
9. Vow trigger 仕様表
10. 条件付き自動進行の停止頻度テスト仕様

---

## 20. 本改訂版の結論

本改訂版は

* 内部状態量は数値で保持し、表示ラベルを閾値導出すること
* Vow 遷移には明示トリガーを持たせること
* 4層テンプレートは具体例込みで設計すること
* 冒険方針の選択主体を明示すること
* Phase 1 から状態が見える簡易マップ改善を入れること

を、本設計の P0 要件として固定する。

以上をもって、本書を `Fantasy Simulator` vNext の詳細基礎設計書とする。
