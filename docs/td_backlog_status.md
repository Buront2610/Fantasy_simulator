# TD-1〜TD-4 Backlog Status (Audit)

最終更新: 2026-04-15

このメモは `docs/implementation_plan.md` の TD-1〜TD-4 について、
「現時点で残っているもの」を先に確認してから実装を進めるための監査ログ。

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

### Remaining

- persistence 上の三重保持（`event_records` + `event_log` + `history`）は互換性のため残置。
- sunset 実施（保存フォーマット縮退）は PR-J/K 前の別バッチで扱う。

## TD-2 SettingBundle Externalization

### Done in code

- `screen_world_lore()` は bundle source 参照へ移行済み。
- `CharacterCreator` の race/job 読み取りは bundle-first + default bundle fallback。
- `world_data` の lore/race/job/default site seed は legacy projection として制約テストで管理。

### Remaining

- authoring 用の bundle 差し替え UX（複数 world package 運用）は未完。
- `ALL_SKILLS` は共有カタログとして `world_data` 依存を継続（非 lore/race/job 領域）。

## TD-3 Responsibility Split (`world.py` / `events.py`)

### Remaining (major)

- `world.py` と `events.py` の内部責務分離（モジュール分割）は未完。
- 互換APIを壊さない分割計画が必要なため、現バッチでは未着手。

## TD-4 Guardrails / Harness / Docs

### Done in this repo state

- architecture constraints: legacy adapter read-path と legacy projection import 制約を強化。
- doc freshness: implementation/architecture/readme の整合監視を追加。
- quality gate `standard`: architecture/doc/harness 系を routine 実行。

### Remaining

- TD-3 が進んだ後の harness 期待値更新（責務分割後の acceptance contract 再調整）。

