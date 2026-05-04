# ADR 0002: PR-K World Change Uses State Machine Boundaries

Status: Accepted for K0-1
Date: 2026-05-03
Plan anchor: `docs/implementation_plan.md` Phase I / PR-K

## Context

PR-K changes are long-lived world history, not one-off flavor lines. Renaming a
location, blocking a route, occupying a site, or shifting an era changes what
future simulation, reports, maps, and story surfaces should see.

Without explicit boundaries, code can drift into direct mutation:

```text
event text -> ad hoc state edit -> UI reads raw fields
```

That shape makes invalid transitions hard to detect and makes save/load
compatibility fragile.

## Decision

PR-K world change should use explicit state machine boundaries.

The standard flow is:

```text
Command
  -> Specification / validation
  -> State Machine transition
  -> Domain Event
  -> WorldEventRecord adapter
  -> ChangeSet
  -> Reducer
  -> World Runtime mutation
  -> Projection / ViewModel
```

World Change logic is a headless domain boundary. It must not depend on UI,
Rich, Textual, renderer, or persistence implementations.

Initial state machine areas:

- Location naming
- Route mutation
- War / occupation
- Era / civilization phase

## Boundary Rules

Location naming:

- `location_id` remains stable across rename.
- A location has one official name at a time.
- Old names are preserved as alias/history data.
- Rename records include old name, new name, and location ID.

Route mutation:

- `route_id` remains stable across block/reopen.
- Route endpoints remain valid location IDs.
- Blocked routes stay queryable and visible from both endpoints.
- `reopened` is an event; runtime status naturally returns to open.

War / occupation:

- faction IDs must reference authored/runtime faction definitions.
- occupied locations must exist.
- controlling faction must reference a known faction when present.
- war relation rules must avoid accidental one-sided state.

Era / civilization phase:

- runtime era references an authored era definition.
- era shift records include old era, new era, and cause metadata.
- prosperity, safety, traffic, mood, and related scores stay in defined ranges.
- missing translation or summary keys should be caught by strict rendering or
  contract tests.

## Consequences

- PR-K slices can be built as small, testable transitions.
- Reducers can be deterministic and inspected by invariant tests.
- Observation projections can depend on stable event/runtime contracts.
- Save/load migration has clearer fields to preserve.
- Some early implementation will look more formal than direct mutation, but it
  reduces long-term ambiguity.

## Alternatives Rejected

Flavor-only events:

- Rejected because reports and maps need lasting state, not only prose.

Direct mutation from simulation events:

- Rejected because validation, event recording, and projection invalidation
  become scattered and hard to test.

UI-driven interpretation:

- Rejected because UI should render view models, not decide domain history.

Full external rule DSL first:

- Rejected for PR-K prerequisites. The domain model and invariants should settle
  before rule authoring becomes data-heavy.

## Fitness Functions / Tests

K0-1 records the decision. Later K0 and PR-K slices should add tests that:

- assert `world_change` modules do not import UI, renderers, or persistence
- assert observation/projection modules do not mutate World Runtime
- assert route state transitions reject invalid endpoint or duplicate-state
  changes
- assert rename keeps location identity stable
- assert war/occupation references existing factions and locations
- assert era shift references authored era definitions
- assert save/load preserves state machine fields and canonical records
- assert locale changes do not alter domain event kinds or runtime state

## Related Documents

- `docs/pr_k_prerequisite_design.md`
- `docs/domain/ubiquitous_language.md`
- `docs/domain/context_map.md`
- `docs/adr/0001-pr-k-event-history.md`
