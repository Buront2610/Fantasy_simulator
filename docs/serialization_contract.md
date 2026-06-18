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
- Display event log: project from `world.event_records`. Legacy
  `world.event_log` input is migration-only and is lifted into event records
  before hydration.
- Event rendering: `WorldEventRecord.summary_key` plus JSON-compatible
  `render_params` is the locale-aware display source when present.
  `description` remains the compatibility fallback text.
  For new structured records, `description` may reflect the locale active when
  the record was created; durable display should prefer `summary_key` and
  semantic `render_params` whenever those fields exist.
  Production display may fall back to `description`; strict rendering paths
  should raise on missing translation keys or params when validating contracts.
- Event causality: `WorldEventRecord.cause_event_ids` is the canonical direct
  cause edge list for query and health checks. Existing
  `render_params["cause_event_id"]` and `render_params["cause_event_ids"]`
  remain compatibility inputs and are normalized into `cause_event_ids` at the
  record boundary.
- Event record order: `world.event_records` is canonical insertion order.
  Projections that need current state consume that order unless a projection
  explicitly documents and tests a stable sort key.
- Event visibility/querying: location queries are derived from canonical record
  metadata, including `location_id`, `location:*` tags, `render_params`
  location IDs (`location_id`, `from_location_id`, `to_location_id`,
  `endpoint_location_ids`), and location-targeted impacts.
- Removed legacy event payloads: `legacy_event_result` and
  `legacy_event_log_entry` may appear in older saves, but current hydration
  ignores them and current serialization never writes them.
- Language evolution: `world.language_evolution_history` beats
  `world.language_runtime_states`.
- Bundle-backed world structure: embedded `world.setting_bundle` site/route
  seeds beat serialized structure; serialized route/grid data may overlay
  runtime state only after validation.
- Bundle-backed terrain: derived terrain cells are omitted. Canonical
  `terrain_cell_mutated` records are the preferred sparse overlay for
  single-cell runtime mutations; a complete `terrain_map` snapshot is still
  emitted when current terrain cannot be rebuilt from bundle terrain plus those
  canonical records.
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
- `cause_event_ids` must be a list of canonical record IDs. It may be empty for
  root events, but non-empty cause IDs should point to existing
  `world.event_records` entries unless the payload is explicitly preserving a
  legacy dangling reference for diagnostics.
- Route visibility must cover both endpoints. Route block/reopen records store
  `from_location_id`, `to_location_id`, `endpoint_location_ids`, and matching
  `location:*` tags so reports and location queries can see the event from
  either connected site.
- Terrain-cell mutation records store semantic cell data, not rendered labels.
  Required `render_params` are `terrain_cell_id`, `x`, `y`, full old/new values
  for `biome`, `elevation`, `moisture`, and `temperature`, plus
  `changed_attributes`. The changed-attribute values must match the old/new
  differences regardless of list order, and sparse replay must reject stale
  records whose old values do not match the replayed cell. Optional params include `location_id`,
  `reason_key`, and `cause_event_id`. Impacts target `terrain_cell` with target
  ID `terrain:<x>:<y>` for each changed attribute. Location-linked mutations
  must also include a `location:<location_id>` tag.
- Compatibility `EventResult` projections may expose canonical `render_params`
  in metadata for legacy readers. Removed legacy metadata is not preserved.
- Migrating pre-current saves may lift legacy `history` and `world.event_log`
  entries into `world.event_records`. Already-migrated legacy records are
  skipped by canonical field identity so repeated migrations do not duplicate
  them.
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
  snapshot is complete for that topology before applying it. Completeness means
  matching width/height, exactly one cell for every in-bounds coordinate, no
  duplicate coordinates, and no out-of-bounds cells. When no snapshot is present,
  load replays canonical `terrain_cell_mutated` records over the derived bundle
  terrain in canonical event order.
- Simulator-owned `world_changes_per_year` is a separate natural world-change
  generation budget for canonical PR-K slices such as route disruption,
  location-linked terrain mutation, natural era shift, civilization drift,
  natural rename, war open/end, and war-driven location-control shift. It must
  round-trip independently from `events_per_year` so ordinary character-event
  density remains comparable across saves. Natural generation should try other
  PR-K generators within the same budget slot when the initially selected
  generator cannot produce a valid change for the current world state.
- Bundle-backed unmodified terrain must stay compact. If the runtime
  `terrain_map` still matches the bundle-derived terrain, new saves omit
  `terrain_map`. If terrain differs but canonical `terrain_cell_mutated` records
  replay to the current terrain, new saves also omit `terrain_map`. Direct
  terrain edits, incompatible grids, malformed terrain records, or any current
  terrain state not reproducible from canonical records fall back to the full
  validated snapshot.
- Route block/reopen records may project endpoint pressure into ordinary saved
  `LocationState` fields and live traces. This does not add a route runtime
  save shape; the route blocked flag remains route state, and the local pressure
  is preserved through the existing location-state serialization contract.
- War declaration/end records may project local pressure into ordinary saved
  `LocationState` fields and live traces. Active faction-war state remains a
  read model derived from canonical `war_declared` / `war_ended` records rather
  than a durable runtime save field.
- Location rename records may project local attention pressure into ordinary
  saved `LocationState` fields and live traces. The canonical name and aliases
  remain the durable identity state; the projected attention pressure uses the
  existing location-state serialization contract.
- Era runtime projections are headless pre-persistence for the current PR-K
  guardrail. Canonical `era_shifted` and `civilization_phase_drifted` records
  may exist, and era/civilization pressure may be projected into saved
  `LocationState` fields, but world-level era runtime fields such as
  `world.era_key`, `world.civilization_phase`, `world.world_scores`, or
  `world.era_runtime` must not be treated as durable save fields until a later
  schema policy is documented. Era-shift commands change the era key; same-era
  phase movement is represented by civilization drift records. If stale
  era/civilization snapshot fields appear in a payload, `world.event_records`
  wins; when no canonical records exist, projections return unknown state
  rather than trusting the stale snapshot. See
  `docs/adr/0003-era-civilization-runtime-persistence.md`.
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
