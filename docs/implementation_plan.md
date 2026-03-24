# Fantasy Simulator 公式実装計画書

**プロジェクト名**: Fantasy Simulator  
**世界名**: Aethoria（エイソリア）  
**版**: Implementation Plan v2.0  
**最終更新**: 2026-03-23 (PR-F 完了)  
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
| `docs/next_version_plan.md` | vNext の目標設計、将来像、To-Be の仕様詳細 | 参照用 |
| `docs/ui_renovation_plan.md` | UI の段階的刷新方針と技術選定 | 参照用 |
| `README.md` | 現在の公開サマリー、起動方法、近接優先事項 | 本書と同期 |

### 2.2 運用ルール

- 実装順の変更、Phase の入れ替え、PR の完了条件変更は **本書を先に更新する**。
- `README.md` は「理想像」ではなく、**現状と近接優先事項を誤読なく伝える文書**として扱う。
- `docs/next_version_plan.md` と `docs/ui_renovation_plan.md` に残る将来像は活かすが、実装順の判断は本書を優先する。
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

- ~~真の月次進行は未完成~~ → PR-B で月次ループ基盤を導入済み。フル月次ループ（NPC行動・依頼生成等）は後続PRで段階的に拡張
- ~~`simulator.py` の責務集中が強い~~ → PR-C で `simulation/` サブパッケージへ mixin ベース分割済み
- イベントストアは方針上 `event_records` を正規とし `history` / `event_log` を補助層と位置づけたが、永続化上はまだ三重保持が残る（PR-E 以降で段階的に縮退予定）
- ~~UI 層と domain 層の分離が不十分~~ → PR-D で `ui/map_renderer.py` + `ui/ui_context.py` 導入。`screens.py` / `main.py` / `character_creator.py` の全 I/O を `InputBackend` / `RenderBackend` 経由に移行完了。ゼロ stdout 漏洩テストで差し替え可能性を証明済み。将来の Rich / Textual 導入基盤が整った
- `AdventureRun` はまだパーティ中心設計に達していない
- live trace / memorial / alias は設計上の受け皿はあるが、実際にデータを生成・投入する処理は未導入
- `CharacterNarrativeState` / `CharacterAbilities` / `Relationship` 構造化は未完了
- ~~`WorldEventRecord.tags` は未導入~~ → PR-B で導入済み。`summary_key` は未導入
- ~~`SIMULATION_DENSITY` は未導入~~ → PR-B で最小版を導入済み
- `NarrativeContext` 主体の文脈依存叙述は未導入
- 高密度 AA マップは未着手

### 3.3 現在の判断

現段階は「Phase E/F を実装した後の品質強化段階」であり、**次は PR-G（AA マップ初版）へ安全に進む段階**である。

したがって今後の優先順位は、次のように定める。

1. ~~文書正本の確定と README 同期~~ → PR-0 完了
2. ~~フォルダ構造・責務境界の整備~~ → PR-A 完了
3. ~~真の月次進行への移行~~ → PR-B 完了
4. ~~イベントストアと参照経路の整理~~ → PR-C 完了
5. ~~UI の責務分離~~ → PR-D 完了
6. ~~その後に Phase E の本体機能へ着手~~ ✅ PR-E/PR-F 完了
7. PR-G（AA マップ初版）へ着手 ← **次はここ**

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

#### まだ未実装、または本格着手前の項目

| 項目 | 状態 | 次の参照 PR |
|---|---|---|
| package 化とフォルダ再配置 | 実装済み | PR-A |
| 共有月次進行基盤（年次一括→月次ループ移行） | 実装済み | PR-B |
| `simulator.py` 分割 + イベントストア正規化（方針確立） | 実装済み | PR-C |
| UI 責務分離 | 実装済み | PR-D |
| パーティ冒険 Phase 1 | 実装済み | PR-E |
| live trace / memorial / alias | 実装済み | PR-F |
| 高密度 AA マップ | 未着手 | PR-G |
| `NarrativeContext` 拡張 | 未着手 | PR-H |

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

---

## 5. 今後の実装方針の全体像

今後の計画は、以下の 6 段階で進める。

> 既存の設計文書では数値ベースの Phase 1〜5 表記も使われていたが、本書では PR 分割と対応づけやすくするため A〜F 表記へ統一する。旧文書の「Phase 4 本体」は本書の Phase E に相当する。

| 旧文書の表記 | 本書の表記 |
|---|---|
| 旧 Phase 4 本体 | Phase E |
| 旧 NarrativeContext 拡張の仕上げ段階 | Phase F |

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

### Phase F: `NarrativeContext` と文脈依存叙述

**目的**:

- relation tags, memorial, world memory を文脈依存のテキストへ接続する
- `NarrativeContext` とテンプレート選択基盤を導入する
- Phase E の成果物を「読む価値のある群像劇」へ引き上げる

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

### 7.7 最後に着手: Phase F

#### F-1. `NarrativeContext` 拡張

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

### PR-G: AA マップ初版

**内容**:

- 世界全体図
- 地域図
- 地点詳細図の初期版

### PR-H: `NarrativeContext` 拡張

**内容**:

- `narrative/context.py`
- テンプレート選択の高度化
- relation tags, memorial, reports との接続

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

### Phase E 着手条件

- ~~月次進行が安定~~ ✅ PR-B 完了
- ~~UI / simulation / persistence の責務境界が見えている~~ ✅ PR-D 完了
- **Phase E 着手可能**

> Phase B 完了後、Phase C / D の進行と衝突しない範囲では Phase E-1 の最小版を並行着手してよい。

### Phase F 着手条件

- memorial / alias / live trace のデータが揃っている
- relation tags や reports を `NarrativeContext` の入力にできる

---

## 10. いま最初に着手すべきこと

PR-0 から PR-F まで完了し、world memory（live trace / memorial / alias）が実装済みである。次に着手すべき実装は **PR-G（AA マップ初版）** である。

**PR-E 完了内容** (2026-03-23):

- `AdventureRun` にパーティフィールドを追加: `member_ids`, `party_id`, `policy`, `retreat_rule`, `supply_state`, `danger_level`
- `is_party` プロパティ: len(member_ids) > 1 で True
- 能力値依存アウトカム: STR/CON → `_compute_injury_chance()`, INT → `_compute_loot_chance()`, danger_level → 危険度修正
- `select_party_policy()`: wisdom/str/int に基づく AI 方針選択
- 撤退基準: `_should_auto_retreat()` による RETREAT_ON_SERIOUS / ON_SUPPLY / ON_TROPHY / NEVER
- 補給状態: `_tick_supply()` (パーティ冒険のみ、ソロは除外)
- `AdventureMixin._start_party_adventure()`: 2-3 人パーティの自動編成（30% 確率）
- 全メンバーの `active_adventure_id` クリア処理
- migration v3 → v4 (旧保存データを後方互換移行)
- i18n: policy 名・supply 状態・パーティ冒険テキスト（en / ja）
- UI: adventure 詳細画面でパーティメンバー・方針・補給状態を表示
- テスト: 17 ケース追加 (ability modifiers, retreat logic, party formation, migration)

**PR-F 完了内容** (2026-03-23):

- `MemorialRecord` dataclass: 死亡地点の永続的墓碑記録 (`world.memorials` dict)
- `LocationState.live_traces`: 冒険者の訪問痕跡（最大10件ローリング）
- `LocationState.aliases`: 重大イベント由来の地名別称（最大3件）
- `World.add_live_trace()` / `add_memorial()` / `add_alias()` / `get_memorials_for_location()`
- `narrative/context.py` 最小 NarrativeContext: `epitaph_for_character()`（職業カテゴリ別碑文）/ `alias_for_event()`（別称生成）
- `AdventureMixin._apply_world_memory()`: 冒険解決時に live trace を記録、死亡時に memorial + alias を生成
- migration v4 → v5: live_traces / memorials を旧保存データへ追加
- i18n: 碑文・別称・地点詳細ビューラベル（en / ja）
- UI: screens.py に「地点の歴史」ビュー追加（alias・memorial・live trace を地点選択形式で表示）
- テスト: 37 ケース追加 (MemorialRecord, add_live_trace, add_memorial, add_alias, round-trip, narrative context, coordinator integration)

**PR-E 留保事項** (Phase 2 以降で対応):

- `spotlighted`/`playable` キャラへのプレイヤー方針選択 UI (設計 §9.3)
- loot_chance による発見物品質の差別化
- パーティ内の個別メンバー負傷追跡

実装順（最新状態）:

1. ~~PR-A: 最小 package 化~~ ✅
2. ~~PR-B: 月次エンジン化~~ ✅
3. ~~PR-C: `simulator.py` 分割 + イベントストア整理~~ ✅
4. ~~PR-D: UI 責務分離~~ ✅
5. ~~PR-E: パーティ冒険 Phase 1~~ ✅
6. ~~PR-F: live trace / memorial / alias~~ ✅
7. PR-G: AA マップ ← **次はここ**
8. PR-H: `NarrativeContext` 拡張

---

## 11. レビューを踏まえた補足判断

今回の評価から、以下を明示的に追記する。

### 11.1 エンジン安定化を content 拡張より優先する

月次の決定論、旧 save 互換、不変条件、観測 UI の情報密度が安定する前に content を増やし始めない。

### 11.2 パーティ冒険は「イベント追加」ではなく「選択の価値を上げるルール実装」として扱う

`policy`、`retreat_rule`、`supply_state`、能力値依存 outcome を噛み合わせ、プレイヤー介入が結果構造を変える段階に達してから拡張する。

### 11.3 world memory は月次進行の信頼性が前提

live trace、memorial、alias は「状態を持つ世界」を厚くするが、月次の因果順が曖昧なままでは蓄積の手触りが弱くなる。よって Phase B を省略しない。

### 11.4 `NarrativeContext` は副次機能ではなく主機能候補として扱う

群像劇の文章が単調な固定テンプレートへ寄ることを防ぐため、Phase F は先送り可能な装飾ではなく、Phase E の成果を読み物として成立させる仕上げ段階とみなす。

---

## 12. 結論

Fantasy Simulator は、すでに基礎設計の多くをコードへ落とし込めている。

PR-0 から PR-F までが完了し、パーティ冒険と world memory（live trace / memorial / alias）まで導入済みである。**次の公式着手対象は PR-G（AA マップ初版）であり、その後 PR-H（NarrativeContext 拡張）へ進む。**

この順序で進めてきた結果、将来のパーティ冒険、世界の長期記憶、AA ベース観測 UI、文脈依存叙述まで、無理なく積み上げられる見込みが高い。

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
| SI-9 | `WorldEventRecord.month` は 1..12 に正規化される | `events.py`, `tests/test_reports.py` |
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

補足:

- `migrations.py` の `CURRENT_VERSION` は 5
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
| PR-7 | `relation_tags` 基礎 | 維持。Phase F の入力基盤 |
| PR-8 | dying / rescue / 死の段階化 | 維持。今後の不変条件に含める |

### 15.2 今後の主対象

| PR | 内容 | この文書での位置づけ |
|---|---|---|
| PR-0 | 文書正本の確定 + README 同期 | ✅ 完了。以後の前提条件 |
| PR-A | 最小 package 化 | ✅ 完了。`fantasy_simulator/` パッケージ構成済み |
| PR-B | 共有月次進行基盤 | ✅ 完了。年次一括処理から月次ループへ移行。`_run_month()` 導入、`advance_months()` で全進行を統一、月次 auto-pause、月付きイベントログ、`SIMULATION_DENSITY` 最小版導入、`WorldEventRecord.tags` 追加。フル月次ループ（NPC行動・依頼生成等）は後続PRで段階的に拡張 |
| PR-C | `simulator.py` 分割 + event store 正規化（方針確立） | ✅ 完了。`simulation/` サブパッケージ導入（mixin ベース分割: engine, timeline, notifications, event_recorder, adventure_coordinator, queries）。`simulator.py` は後方互換ラッパーへ縮小。`WorldEventRecord.impacts` で因果追跡基盤を導入。`World.apply_event_impact()` が影響データを返却。`events_by_kind()` で `event_records` 正規読取パスを追加。`history` は互換アダプター、`event_log` は表示派生物として方針を確立。ただし永続化上はまだ三重保持（`event_records` + `event_log` + `history`）が残る——これは後続 PR で段階的に縮退する |
| PR-D | UI 責務分離 | ✅ 完了。`ui/map_renderer.py` 導入（`MapCellInfo` / `MapRenderInfo` 中間表現 + `build_map_info()` / `render_map_ascii()`）。`ui/ui_context.py` 導入（`UIContext` 依存コンテナ）。`screens.py` / `main.py` / `character_creator.py` の全 I/O を `InputBackend` + `RenderBackend` 経由に移行。直接 `print()` / `input()` を排除し、差し替え可能な UI 基盤を確立。統合テスト（ゼロ stdout 漏洩テスト含む）で証明済み |
| PR-E | パーティ冒険 | ✅ 完了。Party run 基盤（policy / retreat_rule / supply）導入済み |
| PR-F | world memory | ✅ 完了。live trace / memorial / alias 導入済み |
| PR-G | AA マップ | 観測 UI の強化 |
| PR-H | `NarrativeContext` 拡張 | 群像劇の叙述強化 |
