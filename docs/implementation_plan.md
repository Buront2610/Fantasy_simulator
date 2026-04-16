# Fantasy Simulator 公式実装計画書

**プロジェクト名**: Fantasy Simulator  
**世界名**: Aethoria（エイソリア）  
**版**: Implementation Plan v2.0  
**最終更新**: 2026-04-14 (main 反映: PR-I 完了。PR-J / PR-K の前に TD-1〜TD-4 の負債解消を優先)
**位置づけ**: 本書は、現在の実装状況・既存の設計文書・追加レビュー評価を踏まえ、今後の公式な実装順序と文書の正本を定める実装計画書である。

> **文書の優先順位**: 実装順序・完了条件・PR 分割・現状認識の正本は本書とする。`docs/next_version_plan.md` は中長期の設計目標、`docs/ui_renovation_plan.md` は UI 改造方針、`README.md` は現状の公開サマリーを担う。差分が出た場合は、まず本書に追記して吸収し、そのうえで README を同期する。

---

## 1. 本書の目的

本書は、現在の `Fantasy_simulator` の実装状況を踏まえ、今後どの順序で何を実装し、どのような単位で安全に前進させるかを定めるための計画書である。

本計画は、既存の `docs/implementation_plan.md`、`docs/next_version_plan.md`、`docs/ui_renovation_plan.md` の内容を実装現実に合わせて再整理し、次の 4 点を明確にすることを目的とする。

1. 現在の到達点
2. 次に着手すべき実装
3. Phase E 以降へ安全に進むための前提整備
4. 文書の source of truth と README 同期方針

---

## 2. 文書ガバナンスと source of truth

2026-03-23 付の追加レビュー評価で最も重要な指摘は、「実装の遅れ」そのものよりも、**何を現状とみなし、どの文書を優先して意思決定するかが分散し始めている**ことだった。

### 2.1 文書ごとの役割

| 文書 | 役割 | 優先度 |
|---|---|---|
| `docs/implementation_plan.md` | 公式な実装順、PR 分割、着手条件、完了条件、現状認識 | 最優先 |
| `docs/architecture.md` | 現行の依存境界、正規データ源、CI で強制する構造制約の要約 | 本書の補助 |
| `docs/next_version_plan.md` | vNext の目標設計、将来像、To-Be の仕様詳細 | 参照用 |
| `docs/ui_renovation_plan.md` | UI の段階的刷新方針と技術選定 | 参照用 |
| `README.md` | 現在の公開サマリー、起動方法、近接優先事項 | 本書と同期 |

### 2.2 運用ルール

- 実装順の変更、Phase の入れ替え、PR の完了条件変更は **本書を先に更新する**。
- 計画に紐づく調査・実装・レビューは、可能な限り **サブエージェントへ適切に委譲しながら進める**。
- サブエージェントから不足・懸念・追加検証が返った場合は、同じ計画アンカーのまま **自己回帰的に次の調査・実装・レビューへつなぐ**。
- `README.md` は「理想像」ではなく、**現状と近接優先事項を誤読なく伝える文書**として扱う。
- `docs/architecture.md` は本書の代替ではなく、**現行 guardrail を短く機械可読に保つ補助文書**として扱う。
- `docs/next_version_plan.md` と `docs/ui_renovation_plan.md` に残る将来像は活かすが、実装順の判断は本書を優先する。
- 実装で進捗が発生したら、本書の該当節・PR 状態・README などの関連テキストを **同じ変更で同期する**。
- 差分が出たまま次の PR に持ち越さず、PR-0 で確定した正本運用を維持する。

---

## 3. 現状認識

### 3.1 すでに進んでいる領域

現行 main ブランチでは、以下の基礎実装がかなり進んでいる。

- `schema_version` と migration 基盤
- `location_id` ベース参照への移行
- `LocationState` の基礎導入
- `WorldEventRecord` の導入
- `favorite` / `spotlighted` / `playable` の導入
- rumor の基本導入
- 月報 / 年報の基本導入
- dying / rescue / 段階的負傷の基礎導入
- 条件付き自動進行の土台
- 状態表示付きの簡易マップ
- save/load と旧データ互換への配慮

これにより、本プロジェクトはすでに「単純な年次ログ生成 CLI」からは脱しており、vNext の骨格に相当する下地を持っている。

### 3.2 まだ未完成の領域

一方で、設計書が本来目指している完成形には未到達な点も明確である。

- ~~真の月次進行は未完成~~ → PR-B で日単位内部進行へ移行済み。`advance_days()` を正規 API とし、
  `advance_months()` / `advance_years()` はその互換ラッパーになった。NPC 行動・依頼生成等の
  content-rich な sub-month loop は後続 PR で段階的に拡張する
- ~~`simulator.py` の責務集中が強い~~ → PR-C で `simulation/` サブパッケージへ mixin ベース分割済み
- イベントストアは `event_records` を正規とし、`history` / `event_log` は runtime の互換 projection 層として扱う（保存フォーマットからは縮退済み）
- ~~UI 層と domain 層の分離が不十分~~ → PR-D で `ui/map_renderer.py` + `ui/ui_context.py` 導入。`screens.py` / `main.py` / `character_creator.py` の全 I/O を `InputBackend` / `RenderBackend` 経由に移行完了。ゼロ stdout 漏洩テストで差し替え可能性を証明済み。将来の Rich / Textual 導入基盤が整った
- ~~`AdventureRun` はまだパーティ中心設計に達していない~~ → PR-E で party run 基盤（`member_ids`, `party_id`, `policy`, `retreat_rule`, `supply_state`, `danger_level`）を導入済み
- ~~live trace / memorial / alias は未導入~~ → PR-F で world memory（`live_traces`, `memorials`, `aliases`）と地点履歴 UI を導入済み
- `CharacterNarrativeState` / `CharacterAbilities` / `Relationship` の本格構造化は未完了
- ~~`WorldEventRecord.tags` は未導入~~ → PR-B で導入済み。`summary_key` は未導入
- ~~`SIMULATION_DENSITY` は未導入~~ → PR-B で最小版を導入済み
- `NarrativeContext` 主体の文脈依存叙述は未完成であり、PR-I で memorial / alias 生成に
  relation tags / yearly report / rumor / world memory を接続済み。さらに world setting bundle の era 文脈、
  template cooldown、relation tag → ordered candidate list の宣言化と chooser 分離まで完了済み。
  bundle authoring 本体は後続で進める
- aging はランダムイベントから外し、全生存キャラクターへ in-world 1 年ごとに一度適用する deterministic 年次進行へ修正済み。
  world calendar は `SettingBundle` 側へ移し、named / irregular month を扱えるようにした。
  将来の「ゲーム内で参照暦が変わる」イベントに備えて、calendar change history の保存経路も追加済み。
  ただし NPC 行動・依頼生成等の content-rich な sub-month loop は後続で拡張する
- ~~5×5 盤面から離脱した可変サイズ world、terrain / site / route 分離、worldgen PoC は未着手である~~
  → PR-G1 で `World(width, height)`、`terrain_map` / `sites` / `routes`、schema v6 migration を導入済み。
  worldgen PoC 自体は未着手
- ~~高密度 AA マップは未着手であり、現状の地図は依然として「簡易表示」段階に留まる~~
  → PR-G2 で atlas overview / region drill-down / location detail / compact / minimal 表示を導入済み
- ただし現状の観測 UI は依然として「文字列を順に流す CLI」の延長にあり、固定レイアウト、意味色、
  差分再描画、重要局面の局所演出、入力補助といったリッチな CLI の本体は未導入である
- 特に region map は、terrain の近傍切り出し・route 線・nearby sites・landmarks を読める段階までは到達したが、
  設計書が目指す「導線、峠、門、市場、掲示板、墓碑、事故地点、封鎖道、先行パーティの痕跡が判断できる局所地図」
  としては未完成である
- 基礎世界設定の bundle 移行は進行中であり、`screen_world_lore()` は bundle source
  へ移行済み。いっぽう `content/world_data.py` は互換 projection を引き続き保持しているため、
  lore / race / job / location seed の新規参照は bundle 側に寄せ、legacy projection の
  許可先を段階的に縮退する必要がある
- worldgen PoC（seed 固定 terrain generation、外部比較、generated world importer）は未着手であるが、
  これは mainline の観測 UI 改善とは切り分けて進める

### 3.3 現在の判断

現段階は「PR-G2 による三層観測 UI 初版と、PR-H1 による region 観測強化本体まで到達した後の仕上げ段階」である。

terrain / site / route / world memory を読むための基礎データと、atlas / region / detail の三層観測 UI はすでに揃っている。
さらに PR-H1 により、region map には route / closure / danger / rumor / landmark / world memory を
判断支援として圧縮表示する summary 層が加わり、近傍切り出し主体の段階から一歩前進した。

したがって、次の公式着手対象は **TD-1〜TD-4 の負債解消** とする。
ここでは `World.event_records` 正規化、`SettingBundle` の実データ化、`world.py` / `events.py`
の責務圧縮、guardrail / harness / 文書同期の再強化を先に進める。

一方、region map 自体の richer local semantics（門、市場、掲示板、河川、事故地点、痕跡の詳細化など）は、
PR-H1 完了後の後続拡張として扱う。
また、PR-G3 / PR-G4 に相当する worldgen PoC や外部比較実験は、
mainline の UX 改善を止めない範囲で並行任意の技術検証として扱う。

したがって今後の優先順位は、次のように定める。

1. ~~文書正本の確定と README 同期~~ → PR-0 完了
2. ~~フォルダ構造・責務境界の整備~~ → PR-A 完了
3. ~~真の月次進行への移行~~ → PR-B 完了
4. ~~イベントストアと参照経路の整理~~ → PR-C 完了
5. ~~UI の責務分離~~ → PR-D 完了
6. ~~その後に Phase E の本体機能へ着手~~ ✅ PR-E / PR-F 完了
7. ~~PR-G1 / PR-G2（可変ワールド基盤 + 観測UI初版）~~ ✅ 完了
8. ~~PR-H1（region 観測強化本体）~~ ✅ 完了
9. ~~PR-H2（薄い Rich シェル）~~ ✅ 完了
10. ~~PR-I（`NarrativeContext` 拡張）~~ ✅ 完了
11. TD-1〜TD-4: 負債解消（canonical event store / SettingBundle 外部化 / 責務分離 / guardrail 強化） ← **次はここ**
12. PR-J: 世界観設定整理と初期 Setting Bundle 構築
13. PR-K: 動的世界変化（war / renaming / terrain mutation / era shift / civilization drift）
14. PR-G3 / PR-G4 相当の worldgen PoC / 外部比較は並行任意の技術検証として扱う
### 3.4 現在地の追跡用サマリー

計画書を source of truth として扱う以上、読みやすさだけでなく、**何が実装済みで何が未着手かを追跡できる欄**を残す。

#### 実装済みの主要項目

| 項目 | 状態 | 参照 PR |
|---|---|---|
| `schema_version` と migration 基盤 | 実装済み | PR-2 |
| `favorite` / `spotlighted` / `playable` | 実装済み | PR-2.5 |
| `location_id` 移行と `LocationState` 基礎導入 | 実装済み | PR-3 |
| `WorldEventRecord` 導入 | 実装済み | PR-3 |
| 月報 / 年報の基礎 | 実装済み | PR-4 |
| rumor / reliability / 通知密度分離の基礎 | 実装済み | PR-5 |
| 条件付き自動進行の土台 | 実装済み | PR-6 |
| `relation_tags` 基礎 | 実装済み | PR-7 |
| dying / rescue / 段階的負傷 | 実装済み | PR-8 |
| package 化とフォルダ再配置 | 実装済み | PR-A |
| 共有時間進行基盤（年次一括→日次内部進行移行） | 実装済み | PR-B |
| `simulator.py` 分割 + イベントストア正規化（方針確立） | 実装済み | PR-C |
| UI 責務分離 | 実装済み | PR-D |
| パーティ冒険 Phase 1 | 実装済み | PR-E |
| live trace / memorial / alias | 実装済み | PR-F |
| 可変ワールド対応 + 観測 UI 初版 | 実装済み（PR-G1 / PR-G2） | PR-G |
| region 観測強化本体 | 実装済み | PR-H1 |

#### まだ未実装、または本格着手前の項目

| 項目 | 状態 | 次の参照 PR |
|---|---|---|
| `CharacterNarrativeState` / `CharacterAbilities` / `Relationship` の本格構造化 | 未完 | 後続 PR |
| `summary_key` を含む `WorldEventRecord` 表現の拡張 | 未完 | 後続 PR |
| 薄い Rich シェル（固定レイアウト、見出し、余白、強調、意味色、操作導線） | 実装済み | PR-H2 |
| `NarrativeContext` 拡張 | 実装済み（relation tags / reports / world memory 接続 + relation candidate map / chooser 分離完了） | PR-I |
| worldgen PoC / seed 固定 terrain preview / 外部比較 | 未着手 | PR-G3 / PR-G4 |
| region の richer local semantics（門、市場、掲示板、河川、事故地点、痕跡の詳細化） | 未完 | 後続拡張 |

---

## 4. 基本方針

### 4.1 破壊的改修を避ける

本プロジェクトは save/load と migration を重視しているため、大規模な一括破壊ではなく、段階的移行を原則とする。

### 4.2 設計書どおりではなく、設計書に安全に近づく

理想構造を一度に完成させるのではなく、現在の実装規模と保守コストに合わせ、二段階で近づける。

### 4.3 新規機能より先に構造を整える

Phase E のパーティ冒険、live trace、AA マップは魅力的だが、現構造のまま積み増すと保守性が急速に落ちる。

### 4.4 正規データ源を明確にする

今後追加される集計・表示・物語生成は、必ず `World.event_records` を起点とする方向へ統一する。

### 4.5 設計書間の差分は、計画書側で明示的に吸収する

既存の `next_version_plan.md`、`implementation_plan.md`、`ui_renovation_plan.md` の間には、実装の先行・後行に伴う差分がある。今後は「未反映の差分を次で直す」ではなく、**本計画書側に追記して吸収し、実装順と責務を明確に保つ**。

### 4.6 README は常に「現状の顔」と同期する

README は採用済み構造・現在の起動方法・近接優先事項を伝える文書であり、将来像だけを先行して書かない。レビューで指摘されたように、README が古いままだと構造整理よりも関係性深化やローカライズ拡張が先だと誤読されやすいため、PR-0 で確立した同期方針を今後も維持する。

### 4.7 基礎世界設定はコードに固定しない

基礎世界設定がまだ未確定である以上、`WORLD_LORE`, race / job 定義, `DEFAULT_LOCATIONS` を
恒久的なハードコード前提にしない。

- `World` は runtime state を持つ
- lore / race / job / location seed / naming rule は静的な設定 bundle として分離する
- Aethoria は同梱デフォルト設定の 1 つとして扱い、唯一の固定正史実装とはみなさない
- 正本となる基礎世界設定は、将来的に JSON などの外部データとして注入できる形へ寄せる

---

## 5. 今後の実装方針の全体像

今後の計画は、以下の 9 段階（Phase A〜I）で進める。

> 既存の設計文書では数値ベースの Phase 1〜5 表記も使われていたが、本書では PR 分割と対応づけやすくするため A〜I 表記へ統一する。旧文書の「Phase 4 本体」は本書の Phase E に相当する。
>
> **Phase と PR の対応**: Phase A〜D は同名の PR-A〜D と 1:1 対応する。Phase E は PR-E / PR-F / PR-G をまとめた概念段階であり、Phase F 以降は PR 文字と 1 つずれる。対応は下表を参照。

| 旧文書の表記 | 本書の Phase | 対応 PR |
|---|---|---|
| Phase 1〜3 相当（基盤整備） | Phase A〜D | PR-A〜D |
| 旧 Phase 4 本体 | Phase E | PR-E, PR-F, PR-G |
| 観測 UI のリッチ化段階 | Phase F | PR-H |
| 旧 NarrativeContext 拡張の仕上げ段階 | Phase G | PR-I |
| 世界観設定の整理・構築段階 | Phase H | PR-J |
| 歴史的世界変化の導入段階 | Phase I | PR-K |

### Phase A: 最小 package 化とフォルダ構造改善

**目的**:

- 今後の大規模改修に耐える入れ物を先に作る
- 既存 PR-1 相当の未回収部分をここで回収する

### Phase B: 真の月次進行への移行

**目的**:

- 年次ループに month を貼る実装から脱却する
- 設計書の時間モデルへ近づける

### Phase C: イベントストアと責務分離の整理

**目的**:

- `World.event_records` を正規ストアとして明確化する
- `simulator.py` の責務を分割する

### Phase D: UI 層の整理

**目的**:

- domain と presentation を切り離す
- 将来の Rich / Textual / AA UI の基盤を整える

### Phase E: 本体機能着手（従来の Phase 4 相当）

**目的**:

- パーティ冒険
- live trace
- memorial / alias
- 高密度 AA マップ

### Phase F: region 観測強化 + 軽量 Rich シェル

**目的**:

- region map を、設計書が目指す「判断できる局所地図」へ近づける
- atlas / region / detail のうち、もっとも弱い region 層の意味論を優先的に補強する
- 既存の `InputBackend` / `RenderBackend` 抽象を活かしつつ、薄い Rich 化で観測体験を底上げする

### Phase G: `NarrativeContext` と文脈依存叙述

**目的**:

- relation tags, memorial, world memory を文脈依存のテキストへ接続する
- `NarrativeContext` とテンプレート選択基盤を導入する
- 基礎世界設定を `content/world_data.py` の単一ハードコードから外部設定注入可能な形へ寄せる
- Phase F 後の成果物を「読む価値のある群像劇」へ引き上げる

### Phase H: 世界観設定整理と Setting Bundle 構築

**目的**:

- 基礎世界設定が空白のままシミュレーションを始めている状態を解消する
- 最初の正式な world setting bundle を、後付け運用ではなく計画的に整理・構築する
- lore, race, job, geography, culture, naming, glossary を外部データとして編集できる状態にする
- 仮置きの種族定義を、寿命、文化、居住圏、価値観、対外関係まで含む設定へ掘り下げる

### Phase I: 歴史的世界変化の導入

**目的**:

- 戦争、地名変化、地形変化、時代変化、文明変化を「単発フレーバー」ではなく状態変化として扱う
- 地点 state、setting bundle、event record を接続し、世界が長期履歴で変わる構造を導入する
- 観測 UI から「世界が変わった結果」が読み取れるようにする

---

## 6. フォルダ構造改善方針

### 6.1 いきなり最終形にしない

設計書では次のような理想構造が示されている。

- `core/`
- `mechanics/`
- `narrative/`
- `persistence/`
- `ui/`
- `i18n/`

しかし、現状の実装規模では、これを一気に導入すると差分が大きくなりすぎる。そのため、まずは最小 package 化を先行する。

### 6.2 第一段階の新構造

```text
fantasy_simulator/
  __init__.py
  __main__.py
  main.py
  character.py
  world.py
  events.py
  adventure.py
  simulator.py
  persistence/
    save_load.py
    migrations.py
  ui/
    screens.py
    ui_helpers.py
  content/
    world_data.py
  i18n/
    engine.py
    ja.py
    en.py
```

> 第一段階では、`fantasy_simulator/main.py` を実処理本体とし、**ルート直下の `main.py` は互換ラッパーとして残す**。package 化と旧起動方法の互換維持を同時に満たすため、この段階では両方を共存させる。ルート `main.py` の撤去判断は、Phase A 完了後に次の条件を満たした時点で行う。
>
> - CI が `python -m fantasy_simulator` を正式起動経路として通過する
> - README / 利用案内が `python -m fantasy_simulator` 基準へ更新される
> - 既存テストが package import 前提で通過する

### 6.3 第二段階の目標構造

第一段階完了後、必要に応じて以下へ再整理する。

```text
fantasy_simulator/
  __init__.py
  __main__.py
  app/
    cli.py
  core/
    character.py
    world.py
    location.py
    relationships.py
  simulation/
    engine.py
    timeline.py
    notifications.py
  mechanics/
    events.py
    adventure.py
    rumor.py
    quests.py
  narrative/
    reports.py
    context.py
    templates.py
  persistence/
    save_load.py
    migrations.py
    schema.py
  ui/
    screens.py
    ui_helpers.py
    map_renderer.py
    input_backend.py
    render_backend.py
  i18n/
    engine.py
    ja.py
    en.py
  content/
    world_data.py
    defaults.py
```

### 6.4 重要な判断

- `Character` の大分解は急がない
- `simulator.py` は移動だけで済ませず、後続 Phase で責務分割する
- `world_data.py` は早めに `content/` へ移す
- UI の最終整理は `ui/` 作成後に進める

### 6.5 テスト移行方針

package 化では、現状の `conftest.py` と各テストの import がルート直下構成を前提にしている点を必ず処理する。

方針:

- `conftest.py` の `sys.path` 設定を package 構造へ合わせて更新する
- 必要に応じて `__init__.py` で再 export を用意する
- テスト import の一括書き換えは PR-A の作業項目として明示する
- Phase A 完了条件に「既存全テスト通過」を含める

---

## 7. 優先順位つき実装計画

### 7.1 完了済み: PR-0（文書正本確定 + README 同期）

**目的**:

- どの文書を正本とするかを明文化し、今後の実装判断のブレを止める
- README が古い状態像を示し続けることを防ぐ

**作業**:

- `docs/implementation_plan.md` を公式な実装順の正本として明記する
- `docs/next_version_plan.md` と `docs/ui_renovation_plan.md` の役割を整理する
- `README.md` の現状認識と近接優先事項を本書に同期する
- 「README は現状の公開サマリー」「設計書は将来像」「本書は実装順」という分担を固定する

**完了条件**:

- 文書間の優先順位が明記されている
- README が現状と近接優先事項を誤読なく伝える
- 以後の PR が「どの文書に従うべきか」で迷わない

> 状態: 本 PR が PR-0 に相当する。以後はこの状態を前提として PR-A 以降へ進む。

### 7.2 次点: Phase A

#### A-1. `fantasy_simulator/` パッケージの作成

**目的**:

- 実行経路を package ベースへ寄せる
- 将来の import 整理をやりやすくする

**作業**:

- `fantasy_simulator/__init__.py` 作成
- `fantasy_simulator/__main__.py` 作成
- ルート `main.py` を薄い互換ラッパーへ変更し、実処理本体は `fantasy_simulator/main.py` へ寄せる

**完了条件**:

- `python -m fantasy_simulator` で実行できる
- 既存の起動方法も当面壊れない

#### A-2. `persistence/`, `ui/`, `content/`, `i18n/` の先行分離

**目的**:

- 依存の少ない層から先に整理する

**作業**:

- `save_load.py` → `persistence/save_load.py`
- `migrations.py` → `persistence/migrations.py`
- `screens.py` → `ui/screens.py`
- `ui_helpers.py` → `ui/ui_helpers.py`
- `world_data.py` → `content/world_data.py`
- `i18n.py` の分割準備
- `conftest.py` の `sys.path` 設定更新
- テスト import の移行方針策定と必要箇所の一括修正

**完了条件**:

- 既存テスト通過
- import パス整理完了
- ロジック変更なし
- package 化後も save/load と CLI 起動の互換が保たれる
- entrypoint smoke test（`tests/test_entrypoints.py`）で起動経路の自動検証が通る
- 旧 bare import 非互換が README に明示されている

#### A-3. `i18n/` 分離

**目的**:

- テンプレート層拡張に備える

**作業**:

- `i18n/engine.py`
- `i18n/ja.py`
- `i18n/en.py`

**完了条件**:

- 既存翻訳関数の互換維持
- 既存テスト通過

### 7.3 その次: Phase B

#### B-1. `_run_year()` から `_run_month()` への移行

**目的**:

- 真の月次進行を導入する

**作業**:

- `advance_months()` 導入
- `_run_month()` 導入
- `current_month` を表示値ではなく処理本体へ昇格
- rumor、季節補正、冒険進行、通知判定を月次に揃える
- `WorldEventRecord.tags` の最小導入
- `SIMULATION_DENSITY` は Phase B で最小版を導入する。対象は**内部イベント生成密度**のみとし、UI で何を通知するかを決める**通知密度**とは分離する。通知密度は report / notification 側の閾値で扱う。たとえば `SIMULATION_DENSITY` により当月 10 件の内部イベントが `World.event_records` に記録されても、月報や通知に出るのは重大度や watched 対象の条件を満たす 2 件だけ、という「内部では濃く進むが UI は必要な分だけ見せる」設計を守る

**完了条件**:

- 月ごとの処理順が固定される
- rumor aging / generation が自然な月次になる
- 季節補正が実処理順に沿って働く
- Phase E で必要となるイベント分類の基礎が整う

#### B-2. 月次 determinism テスト

**目的**:

- 今後の refactor を安全にする

**作業**:

- seed 固定 world 生成テスト
- seed 固定 12 ヶ月進行テスト
- 月次スナップショット比較

**完了条件**:

- 月次進行の再現性が CI で担保される

### 7.4 並行: Phase C

#### C-1. `simulator.py` の責務分割

**目的**:

- 月次化後の肥大化を防ぐ

**分割先候補**:

- `simulation/engine.py`
- `simulation/timeline.py`
- `simulation/notifications.py`
- `simulation/adventure_coordinator.py`

**完了条件**:

- `simulator.py` が単一責務へ近づく
- 月次処理、通知判定、冒険進行が独立して読める

#### C-2. イベントストア一本化

**目的**:

- 正規データ源を統一する

**方針**:

- `World.event_records` を唯一の正規ストアとする
- `Simulator.history` は互換 adapter
- `World.event_log` は表示派生物

**作業**:

- summary 系の読取元を `event_records` に統一
- report 系の読取元を `event_records` に統一
- 新規コードから `history` / `event_log` を直接読まないようにする
- イベント → 状態影響の追跡構造（`impact_log` もしくは同等の記録）を導入し、因果追跡の基盤を整える

**完了条件**:

- 新規読取側がすべて `event_records` 起点になる
- `history` と `event_log` が補助層として扱われる
- 状態変化の原因を後から辿れる

### 7.5 その後: Phase D

#### D-1. UI 描画責務の切り離し

**目的**:

- domain と表示ロジックを分離する

**作業**:

- `world.render_map()` の責務縮小
- `ui/map_renderer.py` 導入
- `MapRenderInfo` 的な中間表現導入
- `screens.py` を画面遷移中心にする

**完了条件**:

- domain 層が直接文字列描画を持たない方向へ進む
- map 表示の差し替えが可能になる

#### D-2. UI バックエンド抽象

**目的**:

- 将来の Rich / Textual 導入を見据える

**作業**:

- `input_backend.py`
- `render_backend.py`
- 必要に応じて presenter 層導入
- `wcwidth` など幅計算ユーティリティの導入
- ロケール依存の制御フロー解消（表示文ではなくキーで分岐する。例: `action == tr("advance_1_year")` ではなく `action_key == "advance_1_year"` で分岐する）

**完了条件**:

- 入力と描画の依存点が限定される
- UI 改造計画 Phase 0 の未着手項目を本 Phase で回収できる

### 7.6 Phase E: 本体機能へ着手

#### E-1. `AdventureRun` のパーティ化

**目的**:

- 冒険を群像劇の中核装置へ引き上げる

**作業**:

- `member_ids`
- `party_id`
- `policy`
- `retreat_rule`
- `supply_state`
- 能力値依存 outcome
- `playable` / `favorite` / `spotlighted` に応じた意思決定差

**完了条件**:

- 冒険がソロログではなくパーティ行動になる
- プレイヤー介入の意味が増す

#### E-2. live trace / memorial / alias

**目的**:

- 世界の長期記憶を可視化する

**作業**:

- 冒険の痕跡を地点へ残す
- 記念碑・墓碑・地名変化を導入する
- 長期観察の報酬を増やす
- `NarrativeContext` 導入前でも最低限のテンプレート選択で memorial / alias テキストを安定生成する

**完了条件**:

- 土地の歴史が読めるようになる
- 世界が「記憶を持つ」感触が出る

#### E-3. 初期 AA マップ

**目的**:

- 文字ベース観測 UI の中核を強化する

**作業**:

- 地域図
- 地点詳細図
- 痕跡・危険・交通・噂熱の可視化

**完了条件**:

- 現在の簡易マップから一段進んだ観測 UI が成立する

---

#### E-4. 次の公式着手対象の再定義: PR-G（可変ワールド対応 + 地形 PoC + 観測UI初版）

##### 位置づけ

PR-F 完了時点で、`live trace` / `memorial` / `alias` による world memory は導入済みである。  
一方で、現状の観測 UI は依然として「5×5 の地点盤面を表示する」性格が強く、設計書が本来目指している **土地の広がり・導線・履歴・危険の偏りを読む観測体験** には未到達である。

このため、PR-G は単なる「AA マップ初版」ではなく、次の 3 目的を兼ねるものとして再定義する。

1. **現在の遊びに効く観測 UI 強化**
   - `danger` / `traffic` / `rumor_heat` / `world memory` を地図から読めるようにする
2. **5×5 固定盤面からの構造的離脱**
   - 地形と意味地点を分離し、可変サイズ world を受けられるようにする
3. **将来のランダム大陸生成へ繋がる技術実証**
   - terrain generation の PoC を、本体を壊さない形で導入する

この判断は、「マップは装飾ではなく内部状態の可視化である」「world サイズは固定前提にしない」という vNext 設計意図に沿うものであり、設計逸脱ではない。

---

##### PR-G の目的

PR-G の目的は、現行の 5×5 地点グリッドをそのまま豪華にすることではない。  
目指すのは、**広い世界を見ている感覚と、その広さがゲームプレイに効いている感覚を同時に成立させること** である。

そのため、PR-G では次を正式目標とする。

- 地点だけでなく **地形の骨格** が存在する world 表現を導入する
- 地図を見た瞬間に、海岸線、山脈、森林帯、平野、主要街道、危険偏在、噂の熱い地域が分かる
- `memorial` / `alias` / `recent death site` / `live trace` が地図上の意味差として見える
- 主シミュレーションは site / route 側に残しつつ、terrain は導線・危険・季節・視覚表現へ効かせる
- 将来的に seed 固定のランダム地形 / 大陸図生成へ移行できる受け皿を作る

---

##### PR-G の基本原則

###### G-1. 地形セルと意味地点を分離する

現状の 1 マス 1 地点構造では、地形・都市・遺跡・交通路・山脈・海岸線が同一粒度に押し込まれ、没入感より盤面感が先に立ちやすい。  
したがって PR-G では、最低限次の責務分離を導入する。

- **TerrainCell / MacroTile**
  - 高度、湿潤、温度、バイオーム、海岸、河川、通行性などを持つ
- **Site**
  - 都市、村、港、砦、遺跡、ダンジョン入口など、人物と出来事の主舞台
- **RouteEdge**
  - 街道、海路、峠道、季節道、崩落道など、site 間の移動導線

これにより、「山脈の麓に街がある」「海岸都市だけ交易が伸びる」「峠道が冬に死ぬ」「森の外縁で噂が偏る」といった表現を自然に扱えるようにする。

###### G-2. 主シミュレーションは terrain ではなく site / route を主に回す

terrain の細粒度化は視覚表現と world realism に有効だが、すべてのセルを主シミュレーション対象にするとコストが急増する。  
このため PR-G では、主シミュレーションの中心は引き続き **site / route / region** に置き、terrain は以下に効かせる。

- 移動コスト
- 季節補正
- route の可用性
- `danger` / `traffic` / `rumor_heat` の背景補正
- マップ描画
- long-term world flavor

###### G-3. PoC と本体統合を分ける

PR-G は技術実証の側面を持つことを許容する。  
ただし、実験的な地形生成コードと本体の恒久 API を混ぜすぎると保守性が落ちるため、次の分離を行う。

- `fantasy_simulator/worldgen/`
  - 将来本体統合を前提とした軽量 terrain API
- `tools/worldgen_poc/`
  - seed 生成、外部ツール比較、画像 / ASCII 出力などの実験用スクリプト

この分離により、PoC が遊びで終わらず、将来の正式機能へ繋がる構造を保つ。

---

##### PR-G の段階的分割

###### PR-G1: 可変ワールド基盤 + terrain/site 分離

**目的**:
- 5×5 固定盤面から構造的に離脱する
- terrain と site の責務を分ける
- renderer が可変サイズ world を受けられるようにする

**作業**:
- `TerrainCell`（仮名）を導入する
- `Site`（仮名）を導入し、`LocationState` と site の関係を整理する
- `RouteEdge`（仮名）を導入し、site 間導線を地図表現可能にする
- `World` に `terrain_map` と `sites` の両方を持てる構造を追加する
- `MapRenderInfo` / `MapCellInfo` を terrain overlay 前提に拡張する
- world サイズを 5×5 固定前提で扱うコードを洗い出し、可変サイズ前提へ寄せる
- 旧 5×5 world を migration / adapter により読み込めるようにする

**完了条件**:
- world サイズが可変でも壊れない
- site が terrain 上に配置される
- 旧 save / migration 互換が維持される
- terrain と site の分離が renderer と world model 上で成立する

---

###### PR-G2: 観測UI初版

**目的**:
- world memory と地形の広がりが読める観測 UI を成立させる
- 「綺麗な AA」よりも「判断できる地図」を優先する

**基本方針**:
観測 UI は三層を維持する。

1. **ワールド全体図**
   - 海岸線、山脈、森林帯、平野、主要 site、主要 route、危険帯、噂熱、記念物を圧縮表示する
2. **地域図**
   - 選択地点の周辺導線、峠、街道、門、市場、掲示板、墓碑、事故地点などを表示する
3. **地点詳細図**
   - 都市 / 遺跡 / 野外 / ダンジョン入口などの局所状態と最近の痕跡を AA / 準AA で表示する

**ワールド全体図で最低限見せるもの**:
- 山脈
- 海岸線
- 森林帯
- 平野
- site
- route
- `danger_band`
- `traffic_band`
- `rumor_heat_band`
- `has_memorial`
- `has_alias`
- `recent_death_site`

**作業**:
- `map_renderer.py` の world-scale 表現を terrain + site overlay へ更新する
- 凡例を追加する
- 狭幅端末用の簡易表示へフォールバックを実装する
- 色なしでも意味が読める記号設計にする
- `screens.py` から全体図 → 地域図 → 地点詳細図へ掘れる導線を追加する
- `world memory` を地点の履歴ビューと地図表示の両方へ接続する

**完了条件**:
- 地図を見て危険、交通、噂、履歴の偏在が分かる
- world memory が地図上の意味差として見える
- 地図が盤面ではなく地理として認識できる
- CJK 幅崩れなしで表示できる

---

###### PR-G3: 地形生成 PoC

**目的**:
- 将来のランダム大陸生成へ繋がる terrain generation の技術実証を行う
- まだ本体の唯一の world 生成経路にはしない

**PoC の対象**:
- elevation
- moisture
- temperature
- biome
- coast
- mountain chains
- forest distribution
- simple rivers
- site candidate spots

**方針**:
- seed 固定で再現できる
- 出力は JSON / ASCII preview / 任意で画像にする
- 生成物は本体へ読み込めるフォーマットにする
- すべての world をランダム生成へ置換することは本 PR の完了条件に含めない

**想定ファイル**:
- `fantasy_simulator/worldgen/generator.py`
- `fantasy_simulator/worldgen/types.py`
- `tools/worldgen_poc/generate_world.py`
- `tools/worldgen_poc/render_preview.py`

**完了条件**:
- seed 固定で同じ地形が再生成できる
- 生成 terrain から site candidate を抽出できる
- 生成結果を world 表示へ読み込める
- PoC が本体設計の将来候補として評価可能な水準にある

---

###### PR-G4: 外部ツール / 外部生成比較実験（任意だが推奨）

**目的**:
- 自前 terrain 生成だけでなく、外部ツールや外部生成物との比較材料を得る
- どこまで自前で持ち、どこを外部生成で補うべきかを判断する

**作業**:
- 外部生成 world の簡易 importer / converter を試作する
- 自前生成との比較観点を整理する
- Fantasy Simulator に必要なのが「見た目の地図」なのか「ゲームプレイへ効く地理骨格」なのかを比較可能にする

**補足**:
この段階は本体必須ではないが、PoC を技術検証として扱う以上、比較対象を持つことには意味がある。

---

##### PR-G で導入を検討する外部ライブラリ / 外部ツール（設計書未掲載）

以下は現行 `README` / `implementation_plan.md` / `ui_renovation_plan.md` に明示されていない候補であり、PoC を含む PR-G の範囲で検討対象とする。

###### 1. FastNoiseLite
**用途**:
- heightmap
- moisture / temperature 分布
- coastlines の粗さ
- mountain chain の歪み
- seed 固定 terrain generation の軽量実装

**位置づけ**:
- PR-G3 の第一候補
- 本体統合も比較的しやすい
- まずは `tools/worldgen_poc/` 側で評価する

###### 2. WorldEngine
**用途**:
- プレート、降水、侵食、バイオームを含む world generation の比較参照
- 自前生成の設計比較
- オフライン生成ワールドの検証

**位置づけ**:
- 本体常用依存ではなく、比較対象・参照実装寄り
- PoC 的検証で使う価値がある

###### 3. Azgaar’s Fantasy Map Generator
**用途**:
- 地理構造、国家配置、海岸線、地域圏の比較
- 世界観設計の試作補助

**位置づけ**:
- 本体依存ではなく設計支援ツール
- 大陸感や地政学的な広がりを検討する際の外部参照先

###### 4. python-tcod
**用途**:
- 局所地図
- ダンジョン入口
- 地点詳細図
- 局所 AA / 準AA の足場

**位置づけ**:
- continent generation の主軸ではない
- PR-G2 の地点詳細図や後続の局所 map で採用候補になりうる

**採用判断**:
- PR-G では「採用確定」ではなく「PoC の候補」として扱い、比較後に判断する

---

##### PR-G のテスト戦略

**追加すべきテスト**:
- 可変サイズ world の描画テスト
- 旧 5×5 world の互換テスト
- `terrain_map + sites` の変換テスト
- `MapRenderInfo` の terrain overlay テスト
- `memorial / alias / recent_death_site` の地図反映テスト
- CJK 幅崩れテスト
- ワールド全体図 / 地域図 / 地点詳細図のスナップショットテスト
- seed 固定 terrain generation の再現性テスト

**完了条件に含める不変条件**:
- site は有効な terrain 位置上に存在する
- route は有効な site 間だけを結ぶ
- terrain generation の seed 固定結果は再現可能である
- 狭幅端末でも地図表示が破綻しない

---

##### PR-G の完了条件（mainline）

mainline 上では、PR-G の到達点を **PR-G1 / PR-G2 完了** とみなす。
完了条件は次とする。

1. 5×5 固定盤面でなくても world を表現できる
2. terrain と site が world model 上で分離されている
3. 地図が海岸線、山脈、森林帯、平野、主要 route を表現できる
4. `world memory` が地図に反映される
5. ワールド全体図 / 地域図 / 地点詳細図の三層が成立する
6. 可変サイズ world の描画と互換テストが通る

PR-G3 / PR-G4 を行う場合は、追加で次を満たすことを望ましい条件とする。

7. terrain generation PoC が seed 固定再現可能な形で動く
8. PoC が本体へ将来統合可能な API 境界を持つ

---

##### PR-G 後の位置づけ

PR-G は単なる見た目改善 PR ではない。  
これは、今後の `NarrativeContext` 強化、長期的な world realism、ランダム大陸生成、広域交通 / 噂 / 危険伝播の強化へ繋がる **world representation 基盤 PR** と位置づける。

ただし main ブランチはすでに PR-G2 の観測 UI 初版まで到達しており、
直後の mainline で最も不足しているのは region 層の意味密度である。
そのため次段では **PR-H（region 観測強化 + 軽量 Rich シェル）** を先行し、
その後 **PR-I（`NarrativeContext` 拡張）** で「広い世界と歴史を持つ地図の上で、
誰がどこをどう語るか」をテキスト側へ接続する。

### 7.7 次の公式着手対象: Phase F

Phase F は PR 単位では **PR-H1**（region 観測強化本体）と **PR-H2**（薄い Rich シェル）に分割する。
region の意味論強化と Rich UI 化はレビュー観点が異なるため、PR を分けて安全に進める。

#### F-1. PR-H1: region 観測強化本体

**目的**:

- region map を「近傍切り出し」から「導線・危険・履歴を判断できる局所地図」へ引き上げる

**作業**:

- region map における route 接続、封鎖、危険、噂、landmarks、world memory の読みを強化する
- region で「どこを見るべきか」が分かる nearby / route / landmark 要約へ整理する
- `has_memorial` / `has_alias` / `recent_death_site` を region 表示へ接続する
- 主要画面 snapshot、CJK 幅崩れ、狭幅端末フォールバックの自動テスト追加

**完了条件**:

- region が atlas / detail の中間層として意味を持ち、局所判断に使える
- 色なし端末でも意味が落ちない

#### F-2. PR-H2: 薄い Rich シェル

**目的**:

- PR-H1 の成果物を確認・運用しやすくするため、固定レイアウト、強調、余白、操作導線の薄い Rich 化を導入する

**基本方針**:

- 本体 UI 基盤の短期第一候補は **Rich** とする。PR-H2 の最小導入で CJK 幅・既存 renderer との責務分担・snapshot テスト安定性を検証し、問題がなければ採用を確定する
- 入力補助は **prompt_toolkit** を `InputBackend` の背後に限定して段階的に導入する
- **Textual はこの段階では導入しない**。複数ペイン同期、スクロール、ズーム、マウス操作、
  非同期更新が本当に必要になった時点で次段階の採用候補とする
- 日本語英語混在幅は、Rich 経由の表示は Rich に委ね、独自 ASCII / AA レンダラでは `wcwidth` を使って担保する

**作業**:

- `Rich Layout` / `Panel` / `Table` / `Rule` を使った薄い固定レイアウト化
- danger / traffic / rumor / memorial / alias の意味色導入
- 強調、反転、見出し、余白、操作キー表示などの軽量な視線誘導を導入する
- `prompt_toolkit` を `InputBackend` の背後に限定導入
- `wide / compact / minimal` を含む既存観測 UI の段階的載せ替え

**完了条件**:

- 色あり端末では視線誘導が効き、色なし端末でも意味が落ちない
- 薄い Rich 化が region / detail の仕様確定を妨げない
- 現行メニューが文字列入力依存から段階的に脱却する

### 7.8 その後に着手: Phase G

#### G-1. `NarrativeContext` 拡張

**目的**:

- 関係性、噂、土地の記憶、レポートを文脈依存の叙述へ接続する

**作業**:

- `narrative/context.py`
- テンプレート選択の高度化
- relation tags, memorial, reports, world memory との接続

**完了条件**:

- 群像劇の文面が単調な固定テンプレートから脱却する
- 誰が誰をどう見ているかが文章選択に反映される

---

## 8. PR 分割案

### PR-0: 文書正本の確定 + README 同期

**内容**:

- `implementation_plan.md` を公式実装計画の正本として明記する
- `next_version_plan.md` と `ui_renovation_plan.md` の役割を整理する
- README に現状の到達点と近接優先事項を同期する

### PR-A: 最小 package 化

**内容**:

- `fantasy_simulator/` 作成
- `__main__.py`
- `main.py` 互換ラッパー
- `persistence/`, `ui/`, `content/`, `i18n/` の先行分離
- `conftest.py` とテスト import の移行
- entrypoint smoke test の追加（`tests/test_entrypoints.py`）

**性質**:

- できるだけロジック変更なし

**互換範囲の明示**:

- CLI 起動（`python -m fantasy_simulator` / `python main.py`）と save/load の互換は維持
- 旧ルート直下の bare import（例: `from i18n import tr`、`from world import World`）は**非互換**
- すべての import は `fantasy_simulator.*` パッケージパスを使用する（例: `from fantasy_simulator.i18n import tr`）

### PR-B: 月次エンジン化

**内容**:

- `_run_month()` 導入
- 月次処理順の固定
- `WorldEventRecord.tags` の最小導入
- 月次 determinism テスト

### PR-C: `simulator.py` 分割 + イベントストア整理

**内容**:

- `simulation/` 導入
- `event_records` 正規化
- `history` / `event_log` の adapter 化
- `impact_log` ないし同等の因果追跡構造

### PR-D: UI 責務分離

**内容**:

- `map_renderer.py` — 中間表現（`MapCellInfo` / `MapRenderInfo`）と ASCII レンダラー
- `ui_context.py` — `UIContext` 依存コンテナ（`InputBackend` + `RenderBackend` を束ねる）
- `screens.py` の全関数が `ctx: UIContext` を受容し、直接 `print()` / `input()` を排除
- `main.py` も `UIContext` 経由に移行
- `character_creator.py` の対話入力パスも `UIContext` 経由に移行
- `RenderBackend` に `print_wrapped()` / `print_dim()` を追加
- 統合テスト（ゼロ stdout 漏洩テスト含む）で差し替え可能性を証明

### PR-E: パーティ冒険 Phase 1

**内容**:

- `member_ids`
- `policy`
- `retreat_rule`
- `supply_state`
- outcome 改善

### PR-F: world memory

**内容**:

- live trace
- memorial
- alias
- 最小 `NarrativeContext` / テンプレート選択基盤

### PR-G: 可変ワールド対応 + 地形 PoC + 観測UI初版

**内容**:

- PR-G1: 可変ワールド基盤 + terrain/site 分離
- PR-G2: 観測UI初版（世界全体図 / 地域図 / 地点詳細図）
- PR-G3: 地形生成 PoC（並行任意の技術検証）
- PR-G4: 外部ツール / 外部生成比較実験（並行任意の技術検証）

### PR-H1: region 観測強化本体

**内容**:

- region map の意味論強化（route 接続、封鎖、危険、landmarks、world memory、trace の読解性向上）
- region で「どこを見るべきか」が分かる nearby / route / landmark 要約
- CJK 幅崩れと snapshot の自動テスト追加

### PR-H2: 薄い Rich シェル

**内容**:

- region / detail / log / legend の軽量レイアウト整理
- Panel / Table / Rule / Text による薄い画面文法の導入
- danger / traffic / rumor / memorial / alias の意味色導入
- prompt_toolkit を `InputBackend` の背後に限定導入
- `wide / compact / minimal` を含む既存観測 UI の段階的載せ替え

### PR-I: `NarrativeContext` 拡張 + `SettingBundle` 最小 schema

**内容**:

- `narrative/context.py` のテンプレート選択高度化
- relation tags, memorial, reports との接続
- `WorldDefinition` / `SettingBundle` の最小 schema・loader・参照経路の導入
- `screen_world_lore()` を `World` または設定 bundle 起点へ切り替える

> PR-I は「NarrativeContext がどう語るか」と「SettingBundle をどう読み込むか」の仕組み導入に集中する。実際の世界観データの整理・記入は PR-J で行う。

### PR-J: Aethoria 初期 bundle の authoring と data migration

**内容**:

- 最初の正式な Aethoria `SettingBundle` を 1 つ作成する
- lore, era, tone, race, job, site seed, culture, glossary を整理・記入する
- 仮置きの race 定義を再点検し、種族ごとの歴史、寿命感、文化差、地理分布、命名規則を整理する
- 既存 `WORLD_LORE` / `DEFAULT_LOCATIONS` / race / job 定義を bundle へ段階移行する
- 「未確定な設定」「確定した設定」「派生生成に委ねる設定」を分けて管理する
- world lore 画面と初期 world 生成が bundle を参照して動く状態にする

> PR-J は PR-I で導入した schema と loader の上で、実際の世界観を整理して埋める authoring パートである。

### PR-K: 動的世界変化（war / renaming / terrain mutation / era shift / civilization drift）

**内容**:

- faction conflict / war を `WorldEventRecord` と location state に接続する
- 正式地名変更と別称蓄積を分離し、rename history を持てるようにする
- 地形・route・atlas layout の変化を限定的に許可する mutation API を導入する
- era / civilization phase の状態を world 定義と runtime state の両方で持てるようにする
- prosperity / safety / mood / traffic / controlling faction を文明変化へ接続する
- region / atlas / report に「世界がどう変わったか」を出せる view model を追加する

---

## 9. 進捗管理上の判断基準

各 Phase を開始する前に、以下を確認する。

### Phase B 着手条件

- PR-A 完了
- package 化後の CI 安定
- save/load と migration の既存互換が維持されている

### Phase C 着手条件

- `_run_month()` ベースが成立
- 月次テストが通る

### Phase D 着手条件

- ~~`event_records` が正規ストアとして扱える~~ ✅ PR-C 完了
- ~~UI が読みに行くデータ源が整理されている~~ ✅ PR-C 完了
- **Phase D は PR-D で完了済み**

### Phase E 着手条件（PR-E / PR-F / PR-G）

- ~~月次進行が安定~~ ✅ PR-B 完了
- ~~UI / simulation / persistence の責務境界が見えている~~ ✅ PR-D 完了
- **Phase E は PR-E / PR-F / PR-G1 / PR-G2 で完了済み**（PR-G3/G4 は並行任意）

### Phase F 着手条件（PR-H）

- PR-G2 の atlas / region / detail UI が安定している
- `InputBackend` / `RenderBackend` による UI 抽象が維持されている
- 既存の map renderer / presenter を壊さずに載せ替えられる

### Phase G 着手条件（PR-I）

- memorial / alias / live trace のデータが揃っている
- relation tags や reports を `NarrativeContext` の入力にできる
- 基礎世界設定を外部データへ逃がすための最小 schema 方針が定まっている

### Phase H 着手条件（PR-J）

- `WorldDefinition` / `SettingBundle` の最小 schema が動作している
- `screen_world_lore()` が bundle 起点へ切り替わっている
- 既存 world の初期生成が bundle 参照でも破綻しない

### Phase I 着手条件（PR-K）

- `WorldDefinition` / `SettingBundle` に era / culture / faction の置き場所が定義されている
- 正式名称と別称を分ける location naming 方針が定まっている
- terrain / route / atlas を再計算しても save 互換を壊さない migration 方針がある

---

### 10. いま最初に着手すべきこと

PR-0 から PR-G2 まで完了し、可変ワールド基盤、terrain / site / route 分離、
三層観測 UI、world memory 接続まで導入済みである。
さらに PR-H1 により、region map には route / closure / danger / rumor / landmark / world memory を
判断支援として圧縮表示する summary 層が加わり、近傍切り出し主体の段階から一歩前進した。

次に着手すべき実装は **TD-1〜TD-4 の負債解消** である。

その理由は、現在の main ブランチでは PR-I まで完了し、次の世界観拡張や動的世界変化を
安全に進めるには、canonical event store、bundle authoring source、責務境界、guardrail の
ねじれを先に解消する必要があるからである。

一方、region map 自体の richer local semantics
（門、市場、掲示板、河川、事故地点、先行パーティの痕跡の詳細化など）は、
PR-H1 完了後の後続拡張として扱う。

なお、PR-G3 / PR-G4 相当の worldgen PoC と外部比較実験は、
mainline の UX 改善を止めない範囲で並行任意の技術検証として扱う。
その後に PR-J で Aethoria の正式 authoring を進め、PR-K で動的世界変化へ入る。

実装順（最新状態）:

1. ~~PR-A: 最小 package 化~~ ✅
2. ~~PR-B: 月次エンジン化~~ ✅
3. ~~PR-C: `simulator.py` 分割 + イベントストア整理~~ ✅
4. ~~PR-D: UI 責務分離~~ ✅
5. ~~PR-E: パーティ冒険 Phase 1~~ ✅
6. ~~PR-F: live trace / memorial / alias~~ ✅
7. ~~PR-G1: 可変ワールド基盤 + terrain/site 分離~~ ✅
8. ~~PR-G2: 観測UI初版（atlas / region / detail）~~ ✅
9. ~~PR-H1: region 観測強化本体~~ ✅
10. ~~PR-H2: 薄い Rich シェル~~ ✅
11. ~~PR-I: `NarrativeContext` 拡張~~ ✅
12. TD-1〜TD-4: 負債解消 ← **次はここ**
13. PR-J: 世界観設定整理と初期 Setting Bundle 構築
14. PR-K: 動的世界変化（war / renaming / terrain mutation / era shift / civilization drift）
15. PR-G3 / PR-G4: worldgen PoC / 比較実験（並行任意）

## 11. レビューを踏まえた補足判断

今回の評価から、以下を明示的に追記する。

### 11.1 エンジン安定化を content 拡張より優先する

月次の決定論、旧 save 互換、不変条件、観測 UI の情報密度が安定する前に content を増やし始めない。

### 11.2 パーティ冒険は「イベント追加」ではなく「選択の価値を上げるルール実装」として扱う

`policy`、`retreat_rule`、`supply_state`、能力値依存 outcome を噛み合わせ、プレイヤー介入が結果構造を変える段階に達してから拡張する。

### 11.3 world memory は月次進行の信頼性が前提

live trace、memorial、alias は「状態を持つ世界」を厚くするが、月次の因果順が曖昧なままでは蓄積の手触りが弱くなる。よって Phase B を省略しない。

### 11.4 `NarrativeContext` は副次機能ではなく主機能候補として扱う

群像劇の文章が単調な固定テンプレートへ寄ることを防ぐため、Phase G は先送り可能な装飾ではなく、Phase F で整えた観測体験の先に置くべき主機能候補とみなす。

### 11.5 基礎世界設定は Aethoria 固定で終わらせない

現状の `content/world_data.py` は実用上の seed data としては有効だが、基礎世界設定の正本をそこへ固定し続けるべきではない。
本作では「どの世界を舞台にするか」自体が将来の設計余地であるため、Phase G 以降では lore / race / job / location / naming を
外部データ bundle として読み込める方向へ寄せる。

### 11.6 世界観設定の整理・構築は独立した作業として確保する

設定 bundle の仕組みを入れることと、実際に世界観を整理して埋めることは別作業である。
現状は「先にシミュレーションの土台を作る」判断で後者を意図的に後回しにしてきたため、
今後は PR-J を設けて、最初の正式な世界設定を計画的に構築する。
ここでは少なくとも次を埋める。

- 世界のコアコンセプト
- 時代名と基礎歴史
- 種族と職能の位置づけ
- 種族ごとの寿命、文化圏、価値観、命名ルール、他種族との関係
- 地理・文化・命名ルール
- 地点 seed と語彙集

### 11.7 歴史的世界変化は「雰囲気要素」ではなく state machine として入れる

類例としては `Dwarf Fortress` の site 変遷・文明史、`Crusader Kings` 系の戦争と支配変動、
`Caves of Qud` の歴史層と地名の語り直しが参考になる。
本作でもこれらを単なる flavor text にせず、次の順で state として入れる。

1. 地名の別称と正式改称を分離する
2. faction / war / occupation を location state へ接続する
3. prosperity / safety / traffic / mood を文明変化へ接続する
4. terrain / route / atlas の限定的 mutation を許可する
5. era shift を world-level state として導入する

---

## 12. 結論

Fantasy Simulator は、PR-G2 の完了により、terrain / site / route を持つ world representation と、
atlas / region / detail から成る観測 UI 初版まで到達した。

次の公式着手対象は **TD-1〜TD-4 の負債解消** である。
PR-I までで導入した canonical event store 方針、SettingBundle の土台、薄い Rich シェルを
実運用に耐える形へ寄せ、PR-J / PR-K の前に互換 adapter と guardrail を整理する。

さらに PR-J（世界観設定整理と初期 Setting Bundle 構築）で、
実際の基礎世界設定を整理し、空の seed data ではなく、
「何をシミュレートしている世界なのか」が定義された状態へ進める。

その後の PR-K では、
戦争、地名変化、地形変化、時代変化、文明変化といった
「歴史として世界が変わる要素」を正式に state machine 化する。

この順序で進めることで、未確定の region 表現を過度に装飾せずに育てつつ、
worldgen PoC と文脈依存叙述を無理なく次段階へ接続できる見込みが高い。

以上を、今後の公式な実装進行方針とする。

---

## 13. 付録A: Safety Invariant（規範の保持）

本文を読みやすく保つため詳細を付録へ寄せるが、**以下の不変条件は今後もレビューとテストで維持する規範**とする。

| ID | 不変条件 | 根拠 / 主な確認点 |
|---|---|---|
| SI-1 | `character.location_id` は有効な `LocationState.id` を参照する | `tests/test_invariants.py` |
| SI-2 | `world.get_location_by_id(character.location_id)` は `None` を返さない | `tests/test_invariants.py` |
| SI-3 | `WorldEventRecord.location_id` は有効 id または `None` | `tests/test_invariants.py`, `migrations.py` |
| SI-4 | save データには `schema_version` が必ず存在する | `save_load.py`, `tests/test_invariants.py` |
| SI-5 | `dead` キャラは active adventure に残らない | `tests/test_invariants.py` |
| SI-9 | `WorldEventRecord.month/day` は下限のみ正規化（`>=1`）し、上限は calendar-aware 層で扱う | `event_models.py`, `tests/test_reports.py`, `tests/test_event_models.py` |
| SI-10 | `LocationState` の状態量は 0..100 に収まる | `tests/test_invariants.py` |
| SI-11 | `dying` キャラは即死せず `alive=True` を維持する段階を持つ | `tests/test_death_staging.py` |

> 以後の計画書更新で本文を簡略化しても、save 互換・参照整合性・死の段階化に関わるこの付録は削らない。

## 14. 付録B: Migration Chain（正式版）

現行コードの migration chain は次を正式版とする。

| Version | 変更内容 | 状態 |
|---|---|---|
| v0 | `schema_version` なしの旧形式 | 旧 save |
| v1 | `schema_version` を保存形式へ追加 | 実装済み |
| v2 | legacy な location 名文字列を `location_id` へ変換 | 実装済み |
| v3 | `LocationState` 基礎項目、`favorite` / `spotlighted` / `playable`、既存 event record 正規化 | 実装済み |
| v4 | `AdventureRun` のパーティ項目 (`member_ids`, `party_id`, `policy`, `retreat_rule`, `supply_state`, `danger_level`) 追加 | 実装済み |
| v5 | world memory 項目（`LocationState.live_traces`, `world.memorials`）追加 | 実装済み |
| v6 | `terrain_map` / `sites` / `routes` 追加 | 実装済み |
| v7 | `atlas_layout` と site atlas coordinates 追加 | 実装済み |

補足:

- `migrations.py` の `CURRENT_VERSION` は 7
- `save_load.py` は save 時に `CURRENT_VERSION` を書き込み、load 時に `migrate()` を通す
- 新しい schema を追加する場合は、`CURRENT_VERSION` を増やし、対応する `_migrate_vN_to_vN+1` とテストを同時に追加する

## 15. 付録C: 完了済み PR と今後の対応表

文書統治上、「設計だけ存在する項目」と「コード導入済みの項目」を混同しないため、短い対応表を残す。

### 15.1 完了済み

| PR | 内容 | 現在の扱い |
|---|---|---|
| PR-2 | `schema_version` と migration 基盤 | 維持。付録Bの正式 chain に含む |
| PR-2.5 | `favorite` / `spotlighted` / `playable` | 維持。report / pause 判定の土台 |
| PR-3 | `location_id`, `LocationState`, `WorldEventRecord` 基礎 | 維持。以後の正規データ源の前提 |
| PR-4 | 月報 / 年報 / report 基盤 | 維持。`World.event_records` 起点を推進 |
| PR-5 | rumor / reliability / 通知密度分離の基礎 | 維持。Phase B / C の前提 |
| PR-6 | 条件付き自動進行の土台 | 維持。真の月次進行へ接続 |
| PR-7 | `relation_tags` 基礎 | 維持。Phase G の入力基盤 |
| PR-8 | dying / rescue / 死の段階化 | 維持。今後の不変条件に含める |

### 15.2 今後の主対象

| PR | 内容 | この文書での位置づけ |
|---|---|---|
| PR-0 | 文書正本の確定 + README 同期 | ✅ 完了。以後の前提条件 |
| PR-A | 最小 package 化 | ✅ 完了。`fantasy_simulator/` パッケージ構成済み |
| PR-B | 共有時間進行基盤 | ✅ 完了。年次一括処理から日次内部進行へ移行。`advance_days()` を正規 API とし、`advance_months()` / `advance_years()` は calendar-aware な互換ラッパーとして維持。月次 auto-pause 集計、日付きイベントログ、`SIMULATION_DENSITY` 最小版、`WorldEventRecord.tags`、calendar abstraction の土台を導入。content-rich な sub-month loop（NPC行動・依頼生成等）は後続PRで段階的に拡張 |
| PR-C | `simulator.py` 分割 + event store 正規化（方針確立） | ✅ 完了。`simulation/` サブパッケージ導入（mixin ベース分割: engine, timeline, notifications, event_recorder, adventure_coordinator, queries）。`simulator.py` は後方互換ラッパーへ縮小。`WorldEventRecord.impacts` で因果追跡基盤を導入。`World.apply_event_impact()` が影響データを返却。`events_by_kind()` で `event_records` 正規読取パスを追加。`history` は互換アダプター、`event_log` は表示派生物として runtime projection に縮退し、保存フォーマットは canonical `event_records` を正規保持する。 |
| PR-D | UI 責務分離 | ✅ 完了。`ui/map_renderer.py` 導入（`MapCellInfo` / `MapRenderInfo` 中間表現 + `build_map_info()` / `render_map_ascii()`）。`ui/ui_context.py` 導入（`UIContext` 依存コンテナ）。`screens.py` / `main.py` / `character_creator.py` の全 I/O を `InputBackend` + `RenderBackend` 経由に移行。直接 `print()` / `input()` を排除し、差し替え可能な UI 基盤を確立。統合テスト（ゼロ stdout 漏洩テスト含む）で証明済み |
| PR-E | パーティ冒険 | ✅ 完了。Party run 基盤（policy / retreat_rule / supply）導入済み |
| PR-F | world memory | ✅ 完了。live trace / memorial / alias 導入済み |
| PR-G | 可変ワールド対応 + 地形 PoC + 観測UI初版 | ✅ PR-G1 / PR-G2 完了。残件は G3 / G4（並行任意） |
| PR-H1 | region 観測強化本体 | ✅ 完了 |
| PR-H2 | 薄い Rich シェル | ✅ 完了（Rich/入力補助の薄い導入と観測UI自動モード切替） |
| PR-I | `NarrativeContext` 拡張 + 基礎世界設定の外部化土台 | ✅ 完了（relation candidate map・chooser 分離・SettingBundle・era 文脈・cooldown 接続） |
| PR-J | 世界観設定整理と初期 Setting Bundle 構築 | 次の mainline 強化対象 |
| PR-K | 動的世界変化 | war / renaming / terrain mutation / era shift / civilization drift |

## 16. 補遺

本節は、主要 PR で何を導入し、どの論点を前進させたかを追跡するための履歴欄である。
実装順・現時点の優先順位・完了条件の正本は本計画書本文を優先し、
ここでは各 PR の到達点と留保事項を簡潔に記録する。

### PR-E 完了内容（2026-03-23）
- `AdventureRun` にパーティ関連フィールドを追加
  - `member_ids`
  - `party_id`
  - `policy`
  - `retreat_rule`
  - `supply_state`
  - `danger_level`
- `is_party` プロパティを導入し、`len(member_ids) > 1` でパーティ扱いとした
- 能力値依存アウトカムの基礎を導入
  - STR / CON → `_compute_injury_chance()`
  - INT → `_compute_loot_chance()`
  - `danger_level` → 危険度補正
- `select_party_policy()` を追加し、wisdom / str / int に基づく AI 方針選択を導入
- `_should_auto_retreat()` により撤退基準を導入
  - `RETREAT_ON_SERIOUS`
  - `ON_SUPPLY`
  - `ON_TROPHY`
  - `NEVER`
- `_tick_supply()` により補給状態の進行を導入（パーティ冒険のみ、ソロは除外）
- `AdventureMixin._start_party_adventure()` により 2〜3 人パーティの自動編成を導入（30% 確率）
- 全メンバーの `active_adventure_id` クリア処理を導入
- migration v3 → v4 を追加し、旧保存データからの後方互換移行を確保
- i18n を追加
  - policy 名
  - supply 状態
  - パーティ冒険テキスト（en / ja）
- adventure 詳細画面でパーティメンバー・方針・補給状態を表示する UI を追加
- テストを 17 ケース追加
  - ability modifiers
  - retreat logic
  - party formation
  - migration

#### PR-E 留保事項
- `spotlighted` / `playable` キャラへのプレイヤー方針選択 UI（設計 §9.3）
- loot chance による発見物品質の差別化
- パーティ内の個別メンバー負傷追跡

### PR-F 完了内容（2026-03-23）
- `MemorialRecord` dataclass を導入し、死亡地点の永続的墓碑記録（`world.memorials`）を追加
- `LocationState.live_traces` を導入し、冒険者の訪問痕跡を保持できるようにした（最大10件ローリング）
- `LocationState.aliases` を導入し、重大イベント由来の地名別称を保持できるようにした（最大3件）
- `World` に以下の world memory API を追加
  - `add_live_trace()`
  - `add_memorial()`
  - `add_alias()`
  - `get_memorials_for_location()`
- `narrative/context.py` に最小 `NarrativeContext` を導入
  - `epitaph_for_character()`（職業カテゴリ別碑文）
  - `alias_for_event()`（別称生成）
- `AdventureMixin._apply_world_memory()` により、冒険解決時の live trace 記録と、
  死亡時の memorial / alias 生成を導入
- migration v4 → v5 を追加し、live_traces / memorials を旧保存データへ追加
- i18n を追加
  - 碑文
  - 別称
  - 地点詳細ビューラベル（en / ja）
- `screens.py` に「地点の歴史」ビューを追加し、alias / memorial / live trace を地点選択形式で表示できるようにした
- テストを 37 ケース追加
  - `MemorialRecord`
  - `add_live_trace`
  - `add_memorial`
  - `add_alias`
  - round-trip
  - narrative context
  - coordinator integration

### PR-G 完了済み範囲（2026-03-24）
- `terrain.py` を導入し、以下の基礎データ構造を追加
  - `TerrainCell`
  - `TerrainMap`
  - `Site`
  - `RouteEdge`
  - `AtlasLayout`
- `World(width, height)` による可変サイズ world 基盤を導入
- `World.terrain_map` / `sites` / `routes` / `atlas_layout` の永続化を導入
- migration v5 → v6 → v7 を追加し、terrain / site / route / atlas layout の後方互換追加を行った
- `ui/map_renderer.py` に terrain-aware な `MapRenderInfo` と、
  world overview / region / detail 描画を導入
- `ui/atlas_renderer.py` に atlas overview / compact / minimal の各表示モードを導入
- `ui/screens.py` に atlas ベース world map navigation と地点履歴 UI の接続を導入
- presenter / view-model 層の最小導入を行った
- terrain / map observation / migration / variable-size world に関するテストを追加した

### PR-H1 完了内容（2026-03-24）
- region map の判断支援層を強化し、summary に以下の cue を導入
  - route
  - closure
  - danger
  - rumor
  - typed landmark / world memory
- blocked route を open route と分離し、nearby list で
  - open: `<->`
  - blocked: `x->`
  として表示するようにした
- route 表示を location_id ではなく human-readable site 名へ統一した
- danger / rumor の region summary 選定に reachability 優先の policy を導入した
  - open-route reachable sites を優先
  - visible だが直接接続されていない sites を次位
  - blocked-route sites を最後
- landmark summary を generic な 1 行ではなく、typed cue に分解した
  - `Memorial`
  - `Alias`
  - `Trace`
  - `Death-site`
- region summary の表示順を整理し、地図直下で「今ここで注目すべきこと」を先に読めるようにした
- i18n を追加
  - region summary 文言（en / ja）
  - rumor focus 文言（en / ja）
- region / atlas 観測 UI テストを拡張した
  - blocked route 表示
  - open / blocked の優先順位
  - reachability ベース danger / rumor 選定
  - typed landmark 表示
  - snapshot-style 出力確認
  - EN / JA narrow-view 幅制約確認

#### PR-H1 到達点
- region map は「近傍切り出し + route 線 + landmarks」段階から進み、
  route / closure / danger / rumor / world memory を圧縮表示できる
  判断支援層を持つようになった

#### PR-H1 後の残課題
- 薄い Rich シェル（固定レイアウト、見出し、余白、強調、意味色、入力補助）
- richer local semantics
  - 門
  - 市場
  - 掲示板
  - 河川
  - 事故地点
  - 痕跡の詳細化
- worldgen PoC / seed 固定 terrain preview / 外部比較
- `NarrativeContext` の本格拡張
