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
  Production display may fall back to `description`; strict rendering paths
  should raise on missing translation keys or params when validating contracts.
- Event visibility/querying: location queries are derived from canonical record
  metadata, including `location_id`, `location:*` tags, `render_params`
  location IDs (`location_id`, `from_location_id`, `to_location_id`,
  `endpoint_location_ids`), and location-targeted impacts.
- Legacy event log entries: `legacy_event_log_entry` is exact preserved text
  from older saves. It is intentionally not retranslated after locale changes.
- Language evolution: `world.language_evolution_history` beats
  `world.language_runtime_states`.
- Bundle-backed world structure: embedded `world.setting_bundle` site/route
  seeds beat serialized structure; serialized route/grid data may overlay
  runtime state only after validation.
- Bundle-backed terrain: derived terrain cells are omitted unless runtime terrain
  mutations require a complete `terrain_map` snapshot.
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
- World-change runtime mutations are transactional with canonical recording:
  if recording the `WorldEventRecord` fails, route state and location
  rename/control/terrain runtime state plus derived event indexes must remain
  unchanged.
- `render_params` values must be JSON-compatible scalars, lists, or dicts with
  string keys. Store semantic values such as IDs or `null`, not translated
  surface strings, so records can render cleanly in another locale. If a record
  also stores compatibility display labels, it must keep the semantic IDs
  alongside them.
- Route visibility must cover both endpoints. Route block/reopen records store
  `from_location_id`, `to_location_id`, `endpoint_location_ids`, and matching
  `location:*` tags so reports and location queries can see the event from
  either connected site.
- Terrain-cell mutation records store semantic cell data, not rendered labels.
  Required `render_params` are `terrain_cell_id`, `x`, `y`, old/new values for
  changed terrain fields, and `changed_attributes`; optional params include
  `location_id`, `reason_key`, and `cause_event_id`. Impacts target
  `terrain_cell` with target ID `terrain:<x>:<y>` for each changed attribute.
  Location-linked mutations must also include a `location:<location_id>` tag.
- Compatibility `EventResult` projections may expose `render_params` in
  metadata for legacy readers. That metadata is adapter output, not an
  additional durable source of truth.
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
  inventing topology. Unknown serialized route entries that do not target a
  canonical route pair are treated as stale legacy structure and ignored; they
  must never create routes in a bundle-backed world.
- Bundle-backed terrain snapshots are v8-compatible overlays. Load must first
  derive bundle topology, then validate that any serialized `terrain_map`
  snapshot is complete for that topology before applying runtime terrain cell
  mutations. Completeness means matching width/height, exactly one cell for
  every in-bounds coordinate, no duplicate coordinates, and no out-of-bounds
  cells.
- Bundle-backed unmodified terrain must stay compact. If the runtime
  `terrain_map` still matches the bundle-derived terrain, new saves omit
  `terrain_map`; after any terrain-cell mutation, new saves include the full
  validated snapshot rather than a sparse delta list.
- Era and civilization projections are headless pre-persistence for the current
  PR-K guardrail. Canonical `era_shifted` and
  `civilization_phase_drifted` records may exist, but world-level era runtime
  fields must not be treated as durable save fields until a later schema policy
  is documented.
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
