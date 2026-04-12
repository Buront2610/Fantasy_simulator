# PR-I Prep Inventory

PR-I の前提整備として、「今すぐ直すべき漏れ」と「今は触らない legacy」を
切り分けるための棚卸しメモ。

この文書は **全面修正の指示ではない**。PR-I で扱うべき対象、PR-I 以降へ送る対象、
当面 legacy のまま保持する対象を見分けるための inventory である。

## 1. user-facing string で i18n 経由ではないもの

以下は現時点で user-facing だが、`tr()` / `tr_term()` ではなく直接表示されている。

| Surface | Current source | Notes |
| --- | --- | --- |
| world lore 本文 | `fantasy_simulator/content/world_data.py` `WORLD_LORE` | `ui/screens.py` の `screen_world_lore()` が `WORLD_LORE` を直接表示する |
| race の説明文 | `fantasy_simulator/content/world_data.py` `RACES[*][1]` | `screen_world_lore()` が `rdesc` を直接表示する |
| race 名 | `fantasy_simulator/content/world_data.py` `RACES[*][0]` | `screen_world_lore()` では `tr_term(rname)` ではなく `rname` をそのまま見せている |
| stat bonus 表記の stat 名 | `fantasy_simulator/ui/screens.py` lore bonus 行 | `strength`, `intelligence` などのキーをそのまま bonus 行へ出している |
| job の説明文 | `fantasy_simulator/content/world_data.py` `JOBS[*][1]` | job 名自体は `tr_term(jname)` だが説明文 `jdesc` は直接表示 |

### 判断

- これらは **world lore / setting authoring** に近い面なので、PR-I で仕組みだけ整え、
  本格移管は PR-J に回すのが自然。
- とくに `WORLD_LORE`, race/job description は `SettingBundle` へ移す候補だが、
  PR-I の段階では「ロード経路・参照経路を作る」までに留める。

## 2. “narrative layer に移管予定” の面

以下はすでに narrative 側のフックがあり、PR-I で強化対象になる。

| Surface | Current status | PR-I でやること |
| --- | --- | --- |
| `fantasy_simulator/narrative/context.py` `epitaph_for_character()` | 最小テンプレート選択のみ。`relation_hint` / `title_hint` / `favorite` は future hook | relation tags / memorial / report metadata を入力へつなぐ |
| `fantasy_simulator/narrative/context.py` `alias_for_event()` | death/notable の 2 系統のみ。`relation_hint` は future hook | relation hint や event metadata から alias family を分岐可能にする |
| monthly/yearly report の叙述 | `reports.py` 自体は canonical projection として安定 | PR-I では report text を narrative 化しても、選ばれる素材は deterministic に保つ |
| location memory の語り | memorial / alias / trace は world state に保存済み | PR-I では「どう語るか」を narrative layer に寄せるが、state 自体は world 側のまま |

### PR-I 前に固定しておく前提

- summary は **canonical event aggregates** ベース
- report は **year/month scoped projection** ベース
- detail は **location-scoped projection** ベース
- narrative は上記 projection の **見せ方** を変えても、入力素材の選定規則を壊さない

## 2.5 すでに着手した PR-I slice 1

- `narrative/context.py` は memorial / alias 生成時に relation tags を読めるようになった
- `fantasy_simulator/content/setting_bundle.py` に最小 `WorldDefinition` /
  `SettingBundle` dataclass と JSON loader を追加した
- `World.setting_bundle` と `screen_world_lore()` の参照経路を接続した

### PR-I 本体 — 完了

- relation tags / reports / rumors / world memory を narrative 入力へ広げる最小接続 ✅
- `SettingBundle` の era 文脈と template cooldown を memorial / alias 選択へ最小接続 ✅
- relation tags の「誰が誰をどう見ているか」をテンプレート分岐へ増やす ✅
  (spouse / family / savior 専用テンプレート + alias_bond_site を追加)
- PR-J の authoring に備え、bundle の実データ整理はまだ始めない ✅（PR-J へ委譲済み）

## 3. 当面 legacy のまま扱うもの

以下は PR-I の対象に含めない。inventory 上も「今は触るな」の扱い。

| Area | Why legacy のままにするか |
| --- | --- |
| `World.event_log` / `Simulator.history` | save/load 互換と旧 API 互換のため残置。canonical source は `World.event_records` |
| `screen_world_lore()` の `WORLD_LORE` 直読み | PR-I では bundle 参照経路導入まで。authoring 本体は PR-J |
| `content/world_data.py` の大規模整理 | bundle authoring 本体に近く、PR-I を太らせる |
| 既存 summary / report / detail の全面 narrative rewrite | PR-I 前の guardrail を壊しやすい。まず projection contract を固定する |

## 4. PR-I に入る前の “やらないこと”

`docs/implementation_plan.md` の分割に従い、PR-I へ混ぜないものを明示する。

- 本格 worldgen
- `world.py` の大規模分割
- 全文 narrative rewrite
- `SettingBundle` authoring 本体
- dynamic world change

### 意図

PR-I は **`NarrativeContext` 拡張** と **`SettingBundle` 最小 schema / loader / 参照経路**
の導入に集中する。

PR-J で world lore / race / job / site seed などの authoring を行い、
PR-K で動的世界変化を扱う。
