# Risk Register

This register tracks risks that are still relevant to the typed world contract
work and its serialization guardrails.

## Completed Guardrails

- RR-001 route graph contract.
  Status: completed in the current branch worktree.
  Evidence: explicit empty bundle route graphs remain disconnected after
  save/load; route adjacency is owned by `world_route_graph.py`; serialized
  topology rejects duplicate route IDs, duplicate route pairs, malformed route
  scalars, and route overlays whose endpoints disagree with the canonical
  graph.
- Serialization conflict precedence docs and tests.
  Status: completed for Step 6/9.
  Evidence: `docs/serialization_contract.md`, `tests/test_doc_freshness.py`,
  and focused save/load conflict tests cover event adapter precedence and
  language history/cache precedence.
- Locale-aware event rendering contract.
  Status: completed in the current branch worktree.
  Evidence: `event_log` and reports render canonical records through
  `summary_key`/`render_params`; `render_params` rejects non-JSON values and
  keeps faction absence as semantic `null` until display time.
- World-change event quality.
  Status: completed in the current branch worktree.
  Evidence: world-change APIs no-op without appending records when the state is
  unchanged, fail fast rather than storing empty fallback descriptions, and
  roll back state when canonical recording fails.
- Route visibility adapter coverage.
  Status: completed in the current branch worktree.
  Evidence: route block/reopen records carry endpoint IDs and `location:*` tags
  so reports and location queries include both connected sites; currently
  blocked routes are surfaced on the observer dashboard from route-status
  projections until they reopen.
- Terrain snapshot compactness.
  Status: completed for the v8 sparse-overlay save/load contract.
  Evidence: unmodified bundle-derived terrain is omitted from saves; mutated
  terrain with canonical `terrain_cell_mutated` records is replayed as a sparse
  overlay without saving a full `terrain_map`; incompatible direct edits still
  fall back to a complete validated snapshot.
- Terrain-cell mutation contract.
  Status: completed in the current branch worktree.
  Evidence: `World.apply_terrain_cell_change` records
  `terrain_cell_mutated` events with semantic `render_params` and
  `terrain_cell` impacts, mutates runtime `TerrainMap` state, reports through
  the terrain-change category, and is covered by the quality-gate terrain
  mutation target.
- Occupation dashboard projection.
  Status: completed in the current branch worktree.
  Evidence: current location occupation/control state is derived from
  canonical war-map projections and surfaced on the observer dashboard; release
  back to no controlling faction removes the dashboard entry without adding
  durable war or occupation runtime fields.
- Dashboard world-change entries.
  Status: completed in the current branch worktree.
  Evidence: observer dashboard world-change summaries now include recent
  concrete world-change entries rendered from canonical report projections,
  using the same locale-aware event renderer as monthly/yearly report cards.
- Natural era-shift generation.
  Status: completed in the current branch worktree.
  Evidence: the natural world-change driver can spend the
  `world_changes_per_year` budget on `era_shifted` records; those records
  project through era timeline, yearly report, dashboard era status, recent
  world-change entries, and save/load roundtrip without durable era runtime
  fields.
- Natural world-change budget fallback.
  Status: completed in the current branch worktree.
  Evidence: when a selected natural PR-K generator no-ops because the current
  world state cannot support that change, generation tries other PR-K
  generators within the same budget slot before giving up.
- Natural world-change notifications.
  Status: completed in the current branch worktree.
  Evidence: canonical records tagged `world_change` pass notification
  thresholds, and the natural world-change timeline phase appends generated
  records to `pending_notifications` when those thresholds pass. World-change
  notifications also become auto-pause candidates with context, explanatory
  subreason, and a world-dashboard recommendation.
- Event-index write path.
  Status: completed in the current branch worktree.
  Evidence: canonical event append keeps the duplicate-detection record-id set
  current without rebuilding the full mutation-sensitive event signature on
  every write; location/actor/year/month/kind indexes remain read-side derived
  state and rebuild through `EventHistoryIndex.ensure_current()` when queried.
- Era runtime snapshot conflict policy.
  Status: completed for the v8 K0 save/load policy.
  Evidence: new saves omit world-level era/civilization runtime fields; the
  hydrator explicitly discards stale `world.era_key`,
  `world.civilization_phase`, `world.world_scores`, and `world.era_runtime`
  fields; focused save/load tests prove canonical `event_records` win
  conflicts and snapshot-only era runtime fields remain unobserved.

## Remaining Risks

- Completed PR-K mainline status drifts in docs.
  Impact: agents may treat completed PR-K guardrails as unstarted, keep working
  the old active milestone, or skip the new map-screen improvement focus.
  Guardrail: `docs/implementation_plan.md` and README must describe PR-K as
  complete and map-screen improvement as active mainline; PR-K completion
  claims need state-machine, canonical-record, projection/view-model,
  UI/report, and test evidence.
- Canonical event records drift from legacy adapters.
  Impact: reports, summaries, and UI event logs disagree after load.
  Guardrail: `world.event_records` remains canonical; current-schema conflict
  tests reject stale `event_log` precedence; display adapters render canonical
  records through the shared event renderer; route visibility uses endpoint IDs
  and `location:*` tags rather than display text; event-history write-side
  duplicate detection keeps record IDs current while read-side indexes rebuild
  from canonical records before query results are returned.
- PR-K command-boundary IDs drift back to untrimmed strings.
  Impact: route, faction, event, era, or terrain-linked IDs may produce records
  that look different from equivalent loaded legacy strings.
  Guardrail: command builders normalize typed IDs before domain events become
  canonical records, including `cause_event_id` and optional terrain-linked
  `location_id`; authored initial faction relationships use normalized faction
  inspection keys and known site ids before they can seed war projections, and
  authored initial site controllers validate against normalized faction
  inspection keys before they can become `LocationState.controlling_faction_id`
  baselines.
- Locale-aware rendering coverage remains partial for future legacy simulation events.
  Impact: newly-added ordinary event families may display their stored
  compatibility description after load if they skip `summary_key` and
  semantic `render_params`.
  Guardrail: strict event rendering detects broken summary metadata; current
  activity, journey, lifecycle, health, relationship, and combat branches have
  cross-locale save/load replay coverage, and future ordinary event families
  must add semantic params explicitly.
- Language runtime cache diverges from durable history.
  Impact: generated names and endonyms change depending on save shape.
  Guardrail: `language_evolution_history` wins over
  `language_runtime_states`; language docs and tests cover replay.
- Documentation trails code-level contract changes.
  Impact: agents make incompatible changes because the source of truth is
  unclear.
  Guardrail: `tests/test_doc_freshness.py` checks this contract and risk
  register for key precedence terms. README, implementation, and review context
  docs now distinguish completed PR-K mainline work from the active
  map-screen improvement focus; future map/UI slices must keep that wording
  current.
- Hydration precedence changes without regression tests.
  Impact: unchanged save schemas still load differently because canonical
  records, legacy adapters, or derived caches are reconciled in a new order.
  Guardrail: behavior-only hydration changes require focused save/load
  conflict tests even when `CURRENT_VERSION` stays unchanged; schema-version
  bumps still require migration tests and README/agent doc freshness updates.
- Era runtime persistence is intentionally deferred.
  Impact: agents may persist world-level era/civilization fields prematurely,
  creating a schema conflict with the K0 guardrail.
  Guardrail: keep era/civilization projections headless and driven by
  canonical records until a later save policy declares durable runtime fields.
  SettingBundle may author non-durable `civilization_phases` and
  `world_score_keys` rule vocabulary, but stale `world.era_key`,
  `world.civilization_phase`, `world.world_scores`, and `world.era_runtime`
  snapshot data are discarded during hydration and must not override
  `world.event_records`.
  Policy: `docs/adr/0003-era-civilization-runtime-persistence.md`.

## Current Status

- No open blocker for Step 6/9 documentation and conflict-precedence coverage.
- Save schema format was not changed for this step; hydration guardrails and
  derived-cache rebuild behavior were tightened.
- RR-001 route graph is no longer tracked as an open serialization risk.
- Remaining future risk is additive: new PR-K dynamic world state fields must
  declare their canonical source and conflict behavior before persistence
  lands. Terrain mutation uses the v8-compatible sparse-overlay policy
  documented in the serialization contract, with complete `terrain_map`
  snapshots retained as fallback, while era/civilization runtime fields remain
  pre-persistence and are explicitly discarded if stale snapshot fields appear
  in a payload. Route block/reopen, location rename, war declarations, era
  shifts, and civilization drift now have save/load projection/report contracts
  that rely on canonical records rather than durable runtime fields, while
  their derived local pressure is preserved through ordinary saved location
  state.
- Ordinary simulation replay risk is shrinking but not gone: activity,
  journey, lifecycle, health, relationship, and combat slices have semantic
  metadata coverage across their main branches, and future ordinary event
  families should keep adding cross-locale save/load replay tests before
  relying on localized descriptions.
