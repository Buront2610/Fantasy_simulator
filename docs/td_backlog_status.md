# TD-1〜TD-4 Backlog Status (Closed Audit)

最終更新: 2026-04-26

このメモは `docs/implementation_plan.md` の TD-1〜TD-4 について、
負債解消 PR の完了条件と、完了後も維持する guardrail を記録する監査ログ。

## Invariants for this cleanup batch

- 新機能追加なし
- 挙動維持
- save/load 互換維持
- canonical input は `World.event_records`

## TD-1 Canonical Event Store

### Inventory (code-path audit)

- `event_records`
  - canonical write: `World.record_event()`
  - canonical read: `simulation/queries.py` (`get_summary`, `events_by_kind`), `reports.py`
- `event_log`
  - compatibility adapter: `World.get_compatibility_event_log()`
  - UI read path: `simulation/queries.py#get_event_log()` 経由のみ
- `history`
  - compatibility projection: `Simulator.history` (`world.event_records -> EventResult`)
  - legacy adapter call: `QueryMixin.events_by_type()`

### Current debt status

- なし（保存フォーマットは canonical `event_records` を正規保持し、
  `event_log` / `history` は runtime projection へ縮退済み）。

## TD-2 SettingBundle Externalization

### Done in code

- `screen_world_lore()` は bundle source 参照へ移行済み。
- `CharacterCreator` の race/job 読み取りは bundle-first。fallback は
  `world_key == "aethoria"` の互換ケースに限定し、非 Aethoria で空配列なら
  明示エラーにする。
- `world_data` の lore/race/job/default site seed は legacy projection として制約テストで管理。

### Current debt status

- なし。
- authoring 用の bundle 差し替え UX（複数 world package 運用）は PR-J の機能作業。
- `ALL_SKILLS` は共有カタログとして `world_data` 依存を継続するが、非 lore/race/job 領域の互換カタログであり、この負債解消対象からは外す。

## TD-3 Responsibility Split (`world.py` / `events.py`)

### Done in this repo state

- `events.py` から純粋データ契約（`EventResult` / `WorldEventRecord` / `generate_record_id`）を
  `event_models.py` へ抽出し、イベント生成の副作用ロジックと分離した。
- `world.py` の event log adapter は `world_event_log.py` へ抽出し、互換ログ整形/投影を純関数化した。
- event-driven な location state mutation / canonical record append を `world_event_state.py`
  へ抽出し、`World` は orchestration と互換API維持に集中する構造へ再配置した。
- decay / propagation（設計書 §5.6）を `world_state_propagation.py` へ抽出し、
  `World.propagate_state()` は orchestrator に縮約した。
- 既存互換API（`from fantasy_simulator.events import ...`, `World.log_event()`, `World.record_event()`）は維持。
- legacy field の扱い / import 正規ルート / mutable copy 方針は `docs/td3_design_decisions.md` に記録。

### Current debt status

- なし。
- era/faction modifier を rules evaluator へ注入する仕組みは PR-K の動的世界変化機能で扱う。

## TD-4 Guardrails / Harness / Docs

### Done in this repo state

- architecture constraints: legacy adapter read-path と legacy projection import 制約を強化。
- doc freshness: implementation/architecture/readme の整合監視を追加。
- quality gate `standard`: architecture/doc/harness 系を routine 実行
  (`tests/test_event_record_read_policy.py` と `tests/test_map_visible_harness.py` を含む)。
- invalid location_id の統合経路（record -> report -> save/load）を characterization test で固定。
- seeded reproducibility の acceptance として、summary / compatibility event log /
  monthly report / yearly report を同一 seed で一致させる E2E characterization を追加。
- map-visible golden harness として、seeded overview / region / detail の snapshot、
  memorial-heavy world memory snapshot を production の screen helper 経路で固定し、
  save-load-midyear 後の map-visible 同値性も `tests/test_map_visible_harness.py` で固定。

### Current debt status

- なし。
