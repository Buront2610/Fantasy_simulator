# Fantasy Simulator Architecture Guardrails

This document is the short, machine-checkable companion to
[`docs/implementation_plan.md`](./implementation_plan.md).
`implementation_plan.md` remains the source of truth for roadmap and phase
order. This file exists to state the current architectural constraints in a
form that tests can enforce.

## Layer Responsibilities

- `fantasy_simulator/simulation/`: simulation orchestration, timeline
  advancement, notifications, canonical event recording, and query helpers.
- `fantasy_simulator/ui/`: rendering, input abstraction, presenters, view
  models, and CLI screen orchestration.
- `fantasy_simulator/persistence/`: save/load and schema migration.
- `fantasy_simulator/world.py`, `events.py`, `character.py`, `terrain.py`,
  `reports.py`, `rumor.py`: domain and reporting primitives shared by higher
  layers.

## Dependency Rules

- `simulation/` must not import `ui/` or `persistence/`.
- `persistence/` must not import `ui/`.
- Core UI modules (`input_backend.py`, `render_backend.py`, `ui_context.py`,
  `ui_helpers.py`, `presenters.py`, `view_models.py`, `map_renderer.py`,
  `atlas_renderer.py`) must not import `simulation/` or `persistence/`.
- `ui/screens.py` is the allowed composition layer that can depend on
  `simulation/`, `persistence/`, and UI helpers together.
- `world.py.render_map()` is an explicit compatibility wrapper into the UI map
  renderer. It is the current exception and should remain narrow.

## Canonical Event Data

- `World.event_records` is the canonical structured event store.
- `World.event_log` is a compatibility display buffer derived from canonical
  events.
- `Simulator.history` is a legacy `EventResult` cache retained for
  compatibility and save/load continuity.

## Read-Path Rules

- New reporting, rumor, presenter, and view-model code must read from
  `event_records`.
- `events_by_type()` is legacy and incomplete by design. New production code
  must not call it.
- Direct `event_log` reads should stay inside compatibility-oriented query/UI
  paths, not spread into new gameplay or reporting logic.

## Deterministic Harness Expectations

- Seeded simulation behavior must stay reproducible.
- Repo-visible acceptance scenarios should exercise summary/report/map-visible
  outputs, not only low-level state equality.
- README claims about entrypoints, schema version, canonical event store, and
  the next roadmap step should stay aligned with the implementation plan.

## Operational Aids

- `docs/contexts/implementation.md` and `docs/contexts/review.md` are short
  task-mode context files, not new sources of truth.
- `docs/subagent_contract.md` defines the preferred delegation shape for
  focused subagent work.
- `docs/session_handoffs/` is for concise repo-local handoffs; keep entries
  short and factual, anchored to the template, and avoid carrying more than
  the latest relevant dated note.
- `scripts/quality_gate.py` provides `minimal`, `standard`, and `strict`
  verification profiles for agent workflows. The `standard` profile is the
  routine guardrail suite for architecture constraints, quality-gate coverage,
  agent workflow docs, doc freshness, and harness scenarios.
