# ADR 0003: Era/Civilization Runtime Persistence Is Deferred

Status: Accepted for K0 guardrail
Date: 2026-05-04
Plan anchor: `docs/implementation_plan.md` Phase I / PR-K

## Context

PR-K introduces headless era shift and civilization phase drift behavior. The
state machine can update an in-memory era runtime object and writes canonical
`era_shifted` and `civilization_phase_drifted` `WorldEventRecord` entries.

The current save schema is v8. It already persists canonical world event
history, but it does not define durable world-level era runtime fields such as
`world.era_key`, `world.civilization_phase`, `world.world_scores`, or an
`world.era_runtime` object. Adding those fields without a policy would create
two possible sources of truth:

- canonical event history
- a mutable runtime snapshot or derived cache

## Decision

Era and civilization runtime persistence is deferred for schema v8.

The canonical source for era/civilization read models is
`world.event_records`. Projection code must derive the current era,
civilization phase, and timeline entries from canonical `WorldEventRecord`
history.

World-level era runtime fields are not durable save fields in v8. If a save
payload contains `world.era_key`, `world.civilization_phase`,
`world.world_scores`, or `world.era_runtime`, those values are treated as stale
or experimental snapshot data and must not override canonical records.

Conflict precedence:

1. `world.event_records` wins for era/civilization timeline and current
   projection state.
2. Runtime snapshot fields may be used only by future schema policy that
   defines migration, validation, and rebuild behavior.
3. If no canonical era/civilization records exist, projection returns unknown
   era/civilization state rather than trusting stale runtime snapshot fields.

Future persistence may add a derived cache, but it must remain rebuildable from
canonical records or explicitly document why it is canonical. If a future schema
stores both canonical records and a runtime snapshot, load must define whether
to validate-and-rebuild, reject conflicts, or accept snapshot fallback when
history is absent.

## Consequences

- `CURRENT_VERSION` does not change for this guardrail.
- Current saves remain compact and do not gain era/civilization runtime fields.
- Stale experimental payload fields cannot silently change observation output.
- Projection tests define current behavior until a later schema policy replaces
  it.
- Future persistence work must add migration and conflict tests before making
  any era/civilization runtime field durable.

## Alternatives Rejected

Persist world-level era runtime now:

- Rejected because schema v8 does not yet define validation, migration, or
  conflict handling between snapshots and canonical event history.

Use runtime snapshot as fallback when event history is absent:

- Rejected for v8 because it would make experimental or stale fields observable
  without a durable contract.

Treat era/civilization as full event sourcing:

- Rejected for the current guardrail because PR-K uses Event Sourcing lite:
  canonical history plus selected runtime snapshots where explicitly
  documented.

## Fitness Functions / Tests

- New saves omit world-level era/civilization runtime fields even if an in-memory
  object has experimental attributes.
- Loading a payload with conflicting era/civilization snapshot fields still
  builds the projection from canonical `world.event_records`.
- Loading a payload with only stale snapshot fields and no canonical records
  leaves era/civilization projection state unknown.

## Related Documents

- `docs/adr/0001-pr-k-event-history.md`
- `docs/adr/0002-pr-k-state-machine-boundaries.md`
- `docs/serialization_contract.md`
- `docs/risk_register.md`
