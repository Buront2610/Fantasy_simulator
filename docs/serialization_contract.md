# Serialization Contract

This document records the save/load conflict rules that must remain stable while
the world model is split across typed helpers and compatibility adapters.

## Scope

- Save payloads are JSON and are versioned by top-level `schema_version`.
- `fantasy_simulator.persistence.migrations.CURRENT_VERSION` is the code source
  of truth for the current save schema.
- `Simulator.to_dict()` and `World.to_dict()` own new saves.
- `load_simulation()` applies migrations before hydrating `Simulator` and
  `World`.

## Canonical Sources

When duplicated or overlapping serialized fields exist, hydration must follow
this precedence:

- World events: `world.event_records` beats top-level `history` and
  `world.event_log`.
- Display event log: project from `world.event_records`; use `world.event_log`
  only when no records exist.
- Event rendering: `WorldEventRecord.summary_key` plus JSON-compatible
  `render_params` is the locale-aware display source when present.
  `description` remains the compatibility fallback text.
- Legacy event log entries: `legacy_event_log_entry` is exact preserved text
  from older saves. It is intentionally not retranslated after locale changes.
- Language evolution: `world.language_evolution_history` beats
  `world.language_runtime_states`.
- Bundle-backed world structure: embedded `world.setting_bundle` site/route
  seeds beat serialized structure; serialized route/grid data may overlay
  runtime state only after validation.
- Route graph shape: bundle `route_seeds` define the canonical graph when a
  bundle is active. An explicit empty route list means intentionally
  disconnected travel, not "infer default roads".
- Generated endonyms: active bundle plus language runtime/history beats
  serialized `generated_endonym`, except for legacy saves or incompatible grids.

## Conflict Rules

- Current-schema saves with `world.event_records` ignore stale serialized
  `world.event_log` lines. The event log is a read-only compatibility view
  projected from canonical records.
- New world-change APIs are idempotent: if the requested state already matches
  the current state, they do not append a canonical `world_change` record.
- `render_params` values must be JSON-compatible scalars, lists, or dicts with
  string keys. Store semantic values such as IDs or `null`, not translated
  surface strings, so records can render cleanly in another locale.
- Migrating pre-current saves may lift legacy `history` and `world.event_log`
  entries into `world.event_records`. Already-migrated legacy records are
  skipped by payload identity so repeated migrations do not duplicate them.
- If both `language_evolution_history` and `language_runtime_states` are
  present, history wins. Runtime states are a convenience cache and must be
  rebuilt from history when history exists.
- If language history is absent, persisted runtime states may be loaded as the
  best available durable state.
- Bundle-backed topology rebuilds from active bundle seeds, then overlays
  serialized runtime state such as blocked routes when endpoints still match.
  Mismatched or duplicate route overlays must fail load rather than silently
  inventing topology.
- Non-bundle serialized topology is explicit. It must validate site references,
  route endpoint references, duplicate route IDs, duplicate route pairs, and
  self-loops before hydration succeeds.
- For language and endonym details, keep this contract aligned with
  [`docs/language_engine.md`](language_engine.md).

## Guardrails

- Add tests for every new serialized field that can conflict with an older
  adapter, cache, or derived projection.
- Prefer a single canonical durable record plus rebuildable projections.
- Do not add new top-level compatibility payload fields unless a migration
  needs them for old snapshots.
- Preserve backward-load compatibility when increasing `schema_version`.
