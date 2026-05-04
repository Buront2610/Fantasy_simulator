# ADR 0001: PR-K Event History Uses WorldEventRecord As Canonical Source

Status: Accepted for K0-1
Date: 2026-05-03
Plan anchor: `docs/implementation_plan.md` Phase I / PR-K

## Context

PR-K will add dynamic world changes such as route mutation, location renaming,
war, occupation, era shift, and civilization drift. These changes must be
visible in reports and maps, survive save/load, and remain explainable as world
history.

Current `main` already defines `World.event_records` as the canonical structured
event store. `World.event_log` and `Simulator.history` are compatibility
projections. `docs/serialization_contract.md` also records event rendering and
route endpoint visibility rules.

PR-K should build on those guardrails instead of introducing a parallel event
history path.

## Decision

PR-K world-change history uses `WorldEventRecord` as the canonical source.

Important world changes must be recorded as canonical records with semantic
metadata suitable for projection, report, rumor, and locale-aware rendering.
Runtime world state remains saved as a snapshot. PR-K adopts Event Sourcing
lite, not complete event replay as the only persistence mechanism.

Canonical PR-K records should prefer:

- stable `kind`
- date fields
- actor and target IDs where applicable
- affected `location_id` or `location_ids`
- `location:*` tags for location visibility
- `summary_key`
- JSON-compatible `render_params`
- `description` fallback
- optional `cause_event_id`
- compatibility payloads only when needed for old adapter behavior

Route block/reopen must preserve the existing endpoint visibility contract:
records carry route ID, both endpoint IDs, endpoint location IDs, and matching
`location:*` tags so either endpoint can query the event.

## Consequences

- Reports, rumor, atlas, region, and location detail projections have one
  canonical historical input.
- Locale-aware display can use semantic params instead of translated stored
  strings.
- Runtime state and history need consistency checks, because both snapshot and
  canonical history are persisted.
- No-op world-change APIs should not append new records.
- If event recording fails, state mutation must not leave the runtime half
  changed.
- New compatibility fields should be avoided unless a migration or legacy
  adapter needs them.

## Alternatives Rejected

Complete Event Sourcing:

- Rejected for PR-K because current save/load depends on snapshots and migration
  compatibility. Replaying every state from events would be a larger project.

Ad hoc event log strings:

- Rejected because they lose semantic IDs, locale-aware rendering, and reliable
  queryability.

Separate PR-K history store:

- Rejected because it would split reports, save/load conflict rules, and
  adapters away from the existing canonical event model.

## Fitness Functions / Tests

K0-1 records this decision. Later K0 and PR-K slices should add tests that:

- assert `world.event_records` wins over stale `event_log` data on load
- assert route block/reopen records include endpoint IDs and both `location:*`
  tags
- assert rename records include old name, new name, and stable `location_id`
- assert war/occupation records include faction IDs and affected location IDs
- assert render params remain JSON-compatible semantic data
- assert report and observation paths read canonical records or projections
- assert save/load roundtrip preserves both runtime state and canonical history

## Related Documents

- `docs/pr_k_prerequisite_design.md`
- `docs/serialization_contract.md`
- `docs/risk_register.md`
- `docs/architecture.md`
- `docs/domain/context_map.md`
