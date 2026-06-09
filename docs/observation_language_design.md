# Aethoria 観測体験と言語エンジン拡張設計書

**Project**: Fantasy Simulator
**World**: Aethoria
**Status**: current-state-aligned design note
**Role**: 実装順の正本ではなく、現状レビューを反映した補助設計書

`docs/implementation_plan.md` は引き続き、実装順・PR分割・完了条件の
source of truth とする。本書は、追加レビューで示された観測ゲーム化・
噂・地図・PR-K world change・言語エンジン拡張の論点を、現在の
リポジトリ状態に合わせて再整理するための設計メモである。

## 1. 目的

Fantasy Simulator は、すでに「小さなランダムイベントCLI」ではない。
現在のコードベースには、canonical event store、日単位内部進行、
月報・年報、噂、world memory、terrain/site/route、SettingBundle、
PR-K world-change primitives、observer dashboard、言語エンジンが
存在する。

したがって、次の課題は単純な「機能を増やすこと」ではない。

> プレイヤーが、変化する世界の余波を読み取り、限られた注目・調査・
> 介入によって、自分だけの年代記を作れるようにする。

最重要方針は次の一文に集約できる。

> 事件を増やすより、事件の余波を見せる。

本書は、次の2本柱を扱う。

- 観測ゲーム体験: dashboard、reports、rumors、map、auto-pause、
  follow-up action。
- 言語エンジン: language family、semantic root、generated endonym、
  etymology、historical name、地名由来UI。

## 2. 現状適合チェック

レビューの方向性はプロジェクトとかなり合っている。ただし、レビュー文の
一部は現在の作業ツリーより古い。設計判断では次の現状を前提にする。

| レビュー論点 | 現在の状態 | 設計上の扱い |
| --- | --- | --- |
| canonical event store | `World.event_records` が正規ストア。`event_log` と `history` は互換投影。 | 新規report、rumor、map、language-history linkは必ずrecord起点にする。 |
| 通常イベントのsemantic rendering | 多くの通常イベントが `summary_key` と `render_params` を持ち、cross-locale save/load testもある。 | 「未着手PR」ではなく、実装済み基盤の拡張・監査として扱う。 |
| PR-K world change | `world_change/` に command、changeset、state machine、adapter、reducer、freshness check、rollback、projection がある。 | 次は基礎scaffoldではなく、ゲーム体験・UI・人物/噂への波及接続。 |
| era/civilization persistence | runtime persistence は意図的に deferred。projection は canonical record 起点。 | durableなworld-level era runtime fieldは、保存方針とmigrationが決まるまで追加しない。 |
| dashboard | `screen_dashboard.py` と `WorldDashboardView` が存在する。 | 0から作らず、優先度・導線・follow-up actionを強化する。 |
| auto-pause UX | `advance_until_pause()` が理由、補足理由、context、recommended actionsを返す。 | 表示と遷移導線を完成させる。 |
| rumor board | `screen_rumors.py` が一覧、filter、source event、関連locationを扱う。 | event summaryではなく、偏り・不完全性・追跡対象として伸ばす。 |
| SettingBundle authoring CLI | `validate`、`inspect`、`preview-map`、`preview-names`、`diff` がある。 | semantic roots、etymology、language family coverageへ拡張する。 |
| 統計ハーネス | `scripts/simulation_stats.py` がseed固定counterを出せる。 | balance/performance観測へ広げる。 |
| console scripts | `fantasy-simulator` と `fantasy-sim` は `pyproject.toml` に定義済み。 | 追加ロードマップ項目にはしない。 |
| language engine | `language/` にschema、phonology、naming、lexicon、resolver、runtime state、evolution planner、generated endonymがある。 | 次は「それらしい音」ではなく、意味と歴史を持つ地名へ進める。 |

## 3. プロダクト目標

プレイヤーは世界へ何でも命令できる神ではなく、限られた注目を持つ観測者である。

中心ループは次を目指す。

1. 現在の世界状態を読む。
2. 重要な変化、噂、注目人物の危機に気づく。
3. 次に見る対象を選ぶ。人物、場所、道、噂、報告書、地図。
4. まれな選択点では介入する。
5. 時間を進め、世界が新しい「気にすべき理由」を生むまで待つ。
6. 重要な結果を自分だけの年代記として残す。

この方向に寄せると、`favorite`、`spotlighted`、`playable`、rumor
reliability、visibility、route block、location alias、memorial、
generated endonym が孤立機能ではなく、同じゲームループの部品になる。

## 4. 守るべき設計ガードレール

- `World.event_records` は歴史、report、rumor、map、world-change read modelの
  因果源であり続ける。
- `description` は互換fallbackであり、将来機能の正規入力に戻さない。
- report、翻訳、要約、リンク対象になるイベントには `summary_key` と
  JSON互換の `render_params` を持たせる。
- 表示名は可能な限り stable ID から後段で解決する。
- `language_evolution_history` は `language_runtime_states` より優先する。
  runtime states はcacheに近い。
- generated endonym は memory alias と別物として扱う。
- `world_change/` と `observation/` は headless に保ち、UI、persistence、
  Rich、Textualをimportしない。
- save schema変更は、serialization policy、migration test、関連docs同期を
  必須とする。
- era/civilization projection は、保存方針が更新されるまで
  event-record driven に留める。

## 5. 観測ゲーム体験

### 5.1 dashboardを第一級画面にする

現行 `WorldDashboardView` はすでに次を持つ。

- world name、year、month label。
- 生存/死亡人数。
- active adventures と pending choices。
- major events。
- watched actors。
- hot rumors。
- dangerous locations。
- world-change counts。

次の段階では、dashboardが即座に次の3問へ答える必要がある。

```text
なぜ今気にするべきか？
時間経過中に何が変わったか？
次にどこを見ればよいか？
```

目標表示例:

```text
World: Aethoria / Year 1042 / Frostwane

Stop Reason
- Mira is dying near Black Pass

Major Changes
- Black Pass was blocked by a landslide
- Northwatch changed control to the Ashen Concord

Watched
- Mira: dying, Black Pass
- Orven: overdue adventure, Ashwood Edge

Rumor Heat
- North: 3 active rumors
- Black Pass: high spread, mixed reliability

Follow Up
1. Inspect Mira
2. Inspect Black Pass
3. Open rumor board filtered to North
```

実装方針:

- `WorldDashboardView` は headless view model のまま保つ。
- 文字列に埋め込まず、`FollowUpActionView` のようなdata shapeを追加する。
- follow-up は auto-pause recommendations、active rumors、recent
  world-change projection から導出する。
- UI screenは描画と入力遷移を担い、view modelはデータに留める。

### 5.2 auto-pause表示

engineはすでに次のpayloadを返せる。

- `pause_reason`
- `pause_subreasons`
- `supplemental_reasons`
- `pause_context`
- `recommended_actions`

必要なのはUI上の完成である。

```text
Stopped at Year 1042, Month 7

Primary reason:
- Watched actor Mira is dying at Black Pass.

Also notable:
- A route near Black Pass is blocked.
- Northern rumors are spreading quickly.

Recommended:
1. Inspect Mira
2. Inspect Black Pass
3. Review recent events
```

プレイヤーが「なぜ止まったのか」を迷わないことを完了条件にする。

### 5.3 reportを編集された歴史にする

月報・年報はすでに canonical records から生成される。次の品質改善は、
単なるevent listではなく、編集されたhistoryとして圧縮すること。

優先すべき編集軸:

- 注目人物への影響。
- location / route state change。
- rumor spread と reliability。
- death、memorial、alias作成。
- occupation、faction control、terrain mutation、era/civilization change。
- 同じ場所でのactivity集中。

追加候補のview:

- `headline_events`: 3〜5件の編集済み見出し。
- `location_threads`: 場所ごとの因果要約。
- `watched_threads`: 注目人物ごとの要約。
- `world_change_threads`: route/location/terrain/occupation/eraの要約。
- `rumor_threads`: source event ID付きの噂の流れ。

### 5.4 rumorを中核システムにする

現行rumorは reliability、category、source location/event、age、spreadを持つ。
次はrumorをevent recapではなく、不完全な情報として扱う。

欲しい性質:

- 地域ごとの言い換え。
- faction / community bias。
- partial truth。
- occasional misinformation。
- decay、mutation、archive。
- player tracking state。
- map marker / report hook。

同じ事件の複数rumor例:

```text
Canonical event:
Black Pass was blocked by a landslide.

Capital rumor:
Merchants say Black Pass is closed after a mountain road failed.

Frontier rumor:
The mountain swallowed the old road.

Guild rumor:
Black Pass is impassable. Escort fees on the southern detour are rising.
```

追加候補field:

- `audience_key`
- `bias_tags`
- `distortion_level`
- `tracked`
- `related_location_ids`
- `related_faction_ids`

rumor generation は `WorldEventRecord` を起点にし、表示済みdescriptionを
parseして正規情報源にしてはいけない。

### 5.5 mapは意思決定密度を優先する

map改善では、AA表現の細かさより「次に何を見るべきか」が分かることを
優先する。

地図が答えるべき問い:

- どの道が封鎖されたか。
- どこが危険か。
- どこに噂が集中しているか。
- 注目人物が最後にどこへいたか。
- どこで死亡、memorial、aliasが生まれたか。
- faction controlがどこで変わったか。
- generated endonym / historical nameを持つ地点はどこか。

現行の atlas / region / detail は良い土台である。次のmap UIは、
overlayからそのままfollow-up actionへ進めるようにする。

## 6. world changeをゲーム体験へ接続する

PR-K primitives は存在する。次はworld changeを人物、噂、report、questへ
波及させる。

| world change | 波及例 |
| --- | --- |
| route blocked | merchant detour、danger shift、escort rumor増加 |
| location renamed | alias/history更新、旧名/新名がcommunity差として表示 |
| occupation changed | faction rumor、refugee/rescue/spy hook |
| terrain mutated | survey/recovery rumor、map overlay更新 |
| era shifted | report language、calendar/era label、glossary prominence |
| civilization drifted | prosperity/danger/traffic baseline、narrative tone |

初期実装は軽量でよい。ただし、波及はone-off textではなく、semantic record
またはdurable stateとして残す。

## 7. 言語エンジンの目標像

言語エンジンは、単なる名前生成器ではなく、次を管理するエンジンにする。

> 世界内の言語体系、命名文化、地名由来、歴史的呼称、共同体ごとの呼び名。

最終的な流れ:

```text
Language Engine
  -> Language System Generator
  -> Semantic Root / Lexicon Realization
  -> Name / Toponym Generator
  -> Etymology Record
  -> World / UI / Rumor / Chronicle
```

現行で既にあるもの:

- authored language definitions。
- `parent_key` による系統。
- seed syllables、inventories、templates、stems、suffixes、patterns。
- sound shifts と structured sound-change rules。
- runtime language evolution records。
- race / tribe / region による language communities。
- lingua franca fallback。
- `LocationState.generated_endonym` に保存されるgenerated endonym。
- `World.language_status()` によるdebug view。

欠けているのは「意味」の層である。

## 8. 追加したい言語domain

### 8.1 Language Family

`LanguageDefinition.parent_key` は派生関係には使えるが、authoringとUIの
まとまりとして `LanguageFamilyDefinition` が欲しい。

```python
@dataclass(frozen=True)
class LanguageFamilyDefinition:
    family_key: str
    display_name: str
    proto_language_key: str
    origin_region_ids: list[str]
    cultural_tags: list[str]
    phonology_profile_key: str = ""
    naming_profile_key: str = ""
    semantic_domain_tags: list[str] = field(default_factory=list)
```

用途:

- language atlas の grouping。
- bundle coverage check。
- etymology表示。
- worldgen language system generation。

互換方針:

- staticな `SettingBundle` dataとして追加する。
- runtime referenceを導入するまでは既存save dataに影響させない。

### 8.2 Semantic Roots

地名由来には安定した意味rootが必要である。

```python
@dataclass(frozen=True)
class SemanticRootDefinition:
    root_key: str
    meaning_key: str
    gloss_en: str
    gloss_ja: str
    semantic_tags: list[str]
    allowed_roles: list[str]
```

各言語では、共有rootをsurfaceへ実現する。

```python
@dataclass(frozen=True)
class LanguageRootRealization:
    language_key: str
    root_key: str
    surface: str
    archaic_surface: str = ""
    notes: str = ""
```

これにより、意味は言語間で共有し、音形だけを分けられる。

```text
root_key: dark
  Aurelian: melan
  Thornic: kar
  Highland Thornic after sound change: khar
```

### 8.3 Toponym Etymology

完成した地名から後で由来を推測しない。意味からsurfaceを作り、その経路を
保存・投影する。

```python
@dataclass(frozen=True)
class ToponymComponent:
    surface: str
    root_key: str
    meaning_key: str
    gloss: str
    role: str
    archaic_surface: str = ""
```

```python
@dataclass(frozen=True)
class ToponymEtymology:
    etymology_id: str
    location_id: str
    name: str
    name_kind: str
    language_key: str
    language_family_key: str = ""
    community_key: str | None = None
    era_key: str | None = None
    source_type: str = "generated"
    components: list[ToponymComponent] = field(default_factory=list)
    literal_gloss_key: str = ""
    literal_gloss: str = ""
    cultural_note_key: str = ""
    generated_year: int | None = None
    source_event_id: str | None = None
```

表示例:

```text
Kharum
- khar < kar: dark / black
- um: mountain pass
- literal gloss: dark pass
```

### 8.4 Location Name Record

現行は canonical name、aliases、generated endonym を持つ。次は、それらを
すぐ置き換えるのではなく、name historyのread modelを先に作る。

```python
@dataclass(frozen=True)
class LocationNameRecord:
    name_id: str
    location_id: str
    surface: str
    normalized_surface: str
    name_kind: str
    language_key: str = ""
    community_key: str | None = None
    faction_id: str | None = None
    valid_from_year: int = 0
    valid_to_year: int | None = None
    source_event_id: str | None = None
    etymology_id: str | None = None
    is_primary: bool = False
```

`name_kind` 候補:

- `canonical`
- `native`
- `generated_endonym`
- `exonym`
- `historical`
- `nickname`
- `political`
- `rumor`

実装注意:

- `LocationState.generated_endonym` と `LocationState.aliases` は当面残す。
- まずは既存fieldを合成するprojectionとして作り、保存形式変更は後に回す。

### 8.5 Language Community拡張

現行resolverは race、tribe、region を扱う。将来は次を足せる。

- factions。
- occupations。
- religions。
- social strata。

これにより、同じ場所に対して現地民、公文書、商人、占領者、噂ネットワークが
別の名前を持てる。

## 9. 地名生成contract

将来の地名生成は次の流れを守る。

```text
location traits
  -> semantic components
  -> language root realizations
  -> phonological rendering
  -> surface name
  -> etymology record
  -> location-name projection
```

例:

```text
mountain pass + dark + dangerous
  -> dark + pass
  -> kar + um
  -> k -> kh initially
  -> Kharum
  -> etymology: "dark pass"
```

これにより、UI、report、rumor、chronicle exportで、名前の由来を
後から一貫して説明できる。

## 10. 言語UI

### 10.1 location detail

短縮表示:

```text
Black Pass
Native name: Kharum
Etymology: Thornic "khar = dark" + "um = pass"
Known as: Widow's Gate
```

詳細表示:

```text
Toponym: Kharum

Language:
- Highland Thornic
- Thornic family
- Lineage: Old Thornic -> Highland Thornic

Components:
- khar < kar: dark / black
- um: mountain pass

Literal gloss:
- dark pass

History:
- Old records used Kar-Um.
- Year 982: initial k shifted toward kh in Highland Thornic.
- Year 1042: Widow's Gate spread as a rumor nickname after an expedition died.
```

### 10.2 Language Atlas

`World.language_status()` にはすでにdebugに使える材料がある。player-facing版は
language atlasとして整理する。

```text
Thornic Family
├─ Old Thornic
│  ├─ Highland Thornic
│  └─ Ashwood Thornic
└─ Lowland Thornic

Aurelian Family
├─ High Aurelian
└─ Court Aurelian
```

language detailで見せるもの:

- lineage。
- regions。
- communities。
- sound features。
- sample names。
- sample toponyms。
- recent evolution records。
- authored roots / realized roots。

### 10.3 personal knowledge mode

個人モードを深める段階では、characterの言語知識によって表示量を変える。

```python
@dataclass(frozen=True)
class CharacterLanguageKnowledge:
    character_id: str
    language_key: str
    proficiency: int
    literacy: int
    cultural_familiarity: int
```

低い知識:

```text
Native name: Kharum
Meaning: unknown
```

高い知識:

```text
Kharum likely comes from Old Thornic kar-um, "dark pass".
```

これは最初のetymology UIの前提ではなく、中長期のgameplay拡張とする。

## 11. 保存方針

二層に分ける。

静的authoring / generated setting data:

- language families。
- semantic root definitions。
- language root realizations。
- phonology / naming style profiles。

これらは `SettingBundle` または generated bundle output に置く。

runtime historical data:

- location name records。
- event-derived nicknames。
- `source_event_id` を持つ toponym etymologies。
- language evolution history。

これらは、保存schema policyが決まった後に World save data へ入れる。

安全な近接順:

1. static bundle schemaに semantic roots と optional language families を追加する。
2. generated endonymの非永続 etymology generation を追加する。
3. canonical name、generated endonym、aliases、rename recordsを合成する
   read-model projectionを追加する。
4. その後、schema bump付きで `location_name_records` と
   `toponym_etymologies` を永続化する。

この作業に便乗して durableな era/civilization runtime field を追加しない。
era/civilizationは、既存ADRどおり event-record driven projection に留める。

## 12. authoring CLI拡張

既存の content CLI は方向性が正しい。別toolを作らず拡張する。

候補:

```bash
python -m fantasy_simulator.content inspect-language bundle.json
python -m fantasy_simulator.content preview-etymology bundle.json loc_black_pass
python -m fantasy_simulator.content preview-language-atlas bundle.json
python -m fantasy_simulator.content check-language-coverage bundle.json
python -m fantasy_simulator.content preview-roots bundle.json --language highland_thornic
```

`inspect` と `diff` に足したいsummary:

- language family count。
- semantic root count。
- languageごとのroot realization coverage。
- etymology coverageを持つsite。
- native nameはあるがetymologyがないsite。
- region coverageを持たないcommunity。

## 13. 推奨実装slice

### OB-1: auto-pause / dashboard follow-up

目的:

- 現在のpause payloadを、プレイヤーに直接役立つ表示と導線にする。

作業:

- primary reason、supplemental reasons、recommendationsをまとめて表示。
- feasibleなrecommendationをmenu actionへ接続。
  - first passとして dashboard follow-up から character story と location map detail へ直接遷移できるようにした。
- dashboardにrecent world-changeとrumor contextを追加。
- 既存test doublesでfocused UI testsを追加。

### OB-2: report threading

目的:

- reportを編集されたhistoryにする。

作業:

- headline/thread view modelを追加。
- location、watched actor、world-change categoryでcluster。
- raw dataはcanonical record由来のまま保つ。
- 選定reportにsnapshot-style testを追加。

### RM-1: rumor bias / tracking

目的:

- rumorをevent summaryではなく情報源として扱う。

作業:

- tracking stateを追加。`Rumor.tracked` が保存互換で round-trip し、dashboard の hot rumors で優先される。
- optional audience/bias fieldsを追加。`audience_key`、`bias_tags`、`distortion_level` を canonical record 起点で生成し、rumor board detail に露出する。
- canonical recordから複数rumor phrasingを生成。初期 slice では正規 record 由来の tracking metadata を先に固定し、複数 phrasing / audience 別文体は後続で広げる。
- related location/event/faction IDsを露出。`related_location_ids`、`related_event_ids`、`related_faction_ids` を rumor summary/detail から参照できる。

### WK-1: world change ripple hooks

目的:

- PR-K changeを観測体験と軽いsimulation incentiveへ接続する。

作業:

- route blockが近傍locationのdanger/traffic/rumor heatへ影響し、自然発生時は tracked rumor と report rumor thread を即時生成する。
- occupationがrumor/report hookを生む。初期 hook は natural world-change driver の canonical record から tracked rumor を生成する形で共通化済み。
- terrain mutationをdetail/map/reportに出す。location-linked terrain change も同じ tracked rumor hook を通る。
- 新規save fieldはcontract文書なしに追加しない。

### LG-1: etymology DTO / read model

目的:

- すぐsave schemaを変えず、地名由来のdata shapeを作る。

作業:

- `ToponymComponent` と `ToponymEtymology` DTOを追加済み。
- 既存language dataからgenerated endonymのstem/suffix/pattern traceを取り、etymology previewを作る。
- authored native nameは生成traceではなく、著者設定の現地名としてread modelに出す。
- location observation/detailに短いetymology lineを出す。
  - map location detail でも `Name origin` / `地名由来` を表示し、地図から地名由来へ直接たどれるようにした。
- 永続化は追加しない。persistent historyはLG-4へ残す。

### LG-2: semantic roots

目的:

- 音だけでなく、意味から一部の地名を生成する。

作業:

- static `SemanticRootDefinition` と `LanguageRootRealization` を追加済み。
- `dark`、`pass`、`river`、`gate`、`ash`、`old`、`sacred`、
  `market`、`stone` のAethoria rootをseed済み。
- `meaning components -> language roots -> surface` を決定的に生成する
  authoring previewを追加済み。
- content CLI inspectionと `preview-roots` を拡張済み。
- 実際のlocation endonym置換や永続etymologyはLG-4へ残す。

### LG-3: language families

目的:

- 複数言語体系を読める形にする。

作業:

- `LanguageFamilyDefinition` を `SettingBundle` に追加済み。
- `parent_key` を壊さず、`LanguageDefinition.family_key` でlanguageをfamilyへ紐づける。
- language atlas view modelと `preview-language-atlas` を追加済み。
- authoring coverage checkとして family未設定/未知family参照を検出する。
- persistent location name historyやfamily別生成ルールはLG-4以降へ残す。

### LG-4: persistent location name history

目的:

- historical name、exonym、political name、rumor nameをdurableにする。

前提:

- serialization contract と migration plan。

作業:

- `LocationNameRecord` を追加。
- `ToponymEtymology` を永続化。
- `RenameLocationCommand` に optional naming reason、language、faction、
  etymology/source event metadataを接続。
- 旧saveはprojection recordsでhydrateし、aliasesを失わない。

### ST-1: statistics / performance harness

目的:

- balanceとpacingを見える化する。

作業:

- `scripts/simulation_stats.py` をmulti-seed runへ拡張。
- deaths、marriage count、adventure outcomes、event density、rumor count、
  world-change count、max danger、save size、runtimeを収集。
- thresholdは最初はadvisoryに留める。
- slow benchmarkは通常unit testsから分ける。

## 14. 推奨順序

1. OB-1: auto-pause/dashboard follow-up。
2. LG-1: persistenceなしのetymology DTO/read model。
3. WK-1: PR-K ripple hooks。
4. OB-2: edited report threads。
5. LG-2: semantic roots。
6. RM-1: rumor bias/tracking。
7. ST-1: broader statistics harness。
8. LG-3: language families。
9. LG-4: persistent location name history。

理由:

- OB-1はengine payloadが既にあり、最短で体験改善できる。
- LG-1はschema変更前にetymology UIの価値を検証できる。
- WK-1は既存PR-K primitivesを「見える面白さ」へ変える。
- persistent name historyはprojectionの形が固まってからでよい。

## 15. 未決定事項

- watched actors / watched regions / tracked rumors / chronicle pins を
  明示的な観測resourceとして制限するか。
- rumorは意図的に嘘をつくべきか、初期版はpartial truthとbiased phrasingに
  留めるか。
- language familiesはauthored、generated、または両方にするか。
- generated endonym etymologyはbundle dataから再計算するか、歴史的drift保持のため
  生成時に保存するか。
- location rename時、古いgenerated endonymを自動でhistorical nameにするか。
- personal mode前に、characterごとのlanguage knowledgeをどこまで入れるか。

## 16. 成功条件

この設計が効いている状態では、プレイヤーが次に答えられる。

```text
何が変わったのか？
誰が影響を受けたのか？
どこで起きたのか？
どんな噂が生まれたのか？
この場所はどんな名前を持ち、それはなぜなのか？
次に何を見ればよいのか？
なぜシミュレーションが止まったのか？
```

言語エンジンについては、次の状態を目指す。

```text
この土地は単に Kharum と呼ばれるのではない。
この言語、この共同体、この歴史が、その名前を定着させた。
```

この段階で、言語エンジンは命名utilityではなく、Aethoriaのworld memoryの
一部になる。
