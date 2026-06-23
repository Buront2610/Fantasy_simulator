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
  - `fantasy_simulator/world.py`, `character.py`, `events/`, `adventure/`,
    `terrain/`, `reports/`, and `rumor/`: public facades and domain/reporting
    primitives shared by higher layers.
  - `character_model/`, `combat_system/`, `world_map/`, and the split
    `world_*` packages hold the narrower implementation surfaces behind those
    public facades.
- `fantasy_simulator/world_change/`: headless PR-K command, state machine,
  event-adapter, changeset, and reducer primitives for dynamic world changes.
- `fantasy_simulator/observation/`: headless read-model projections for reports,
  atlas/region/detail views, story, and rumor surfaces.
- `fantasy_simulator/world_map/`: headless map read models, ASCII projection,
  and local map generation. UI modules render these payloads but should not own
  the projection logic.

## Dependency Rules

- `simulation/` must not import `ui/` or `persistence/`.
- `persistence/` must not import `ui/`.
- Root domain modules under `fantasy_simulator/*.py` must not import `ui/`;
  `fantasy_simulator/main.py` is the CLI composition-root exception.
- `world_change/` must not import `ui/`, `persistence/`, Rich, or Textual.
- `observation/` must not import `ui/`, `persistence/`, Rich, or Textual.
- `world_map/` must not import `ui/`, `simulation/`, `persistence/`, Rich, or
  Textual.
- Core UI modules (`input_backend.py`, `render_backend.py`, `ui_context.py`,
  `ui_helpers.py`, `presenters.py`, `view_models.py`, `map_renderer.py`,
  `atlas_renderer.py`) must not import `simulation/` or `persistence/`.
- `ui/screens.py` is the allowed composition layer that can depend on
  `simulation/`, `persistence/`, and UI helpers together.
- `world.py.render_map()` is a backward-compatible wrapper around the
  renderer-agnostic map snapshot and root ASCII renderer. It must not import
  `ui/`.

## Canonical Event Data

- `World.event_records` is the canonical structured event store.
- Removed legacy event payloads are migration-only inputs. Current
  `WorldEventRecord` serialization must not persist `legacy_event_result` or
  `legacy_event_log_entry`.
- `World.event_log` is a read-only projection derived from canonical events.
- Legacy world mutation helpers such as `rename_location()`,
  `set_route_blocked()`, and `set_location_controlling_faction()` are
  compatibility paths. New production write paths should use canonical
  world-change commands, changesets, and reducers.

## Read-Path Rules

- New reporting, rumor, presenter, and view-model code must read from
  `event_records`.
- Direct `event_log` reads should stay inside text-log query/UI paths, not
  spread into new gameplay or reporting logic.

## Event Projection Inventory

- `World.event_log`: read-only runtime projection from canonical records; load
  paths still accept older snapshots that stored `world.event_log` by migrating
  those lines into records.

## Sunset Conditions

- Keep backward-load compatibility for older snapshots that still contain
  `history`/`event_log`.
- New snapshots must persist canonical `event_records` as the event source of
  truth.
- Event-impact / propagation rules are loaded from `SettingBundle` when
  provided, with bundled defaults as fallback.
- PR-K world-change event records must satisfy the registered
  `world_change.event_contracts` render-param, tag, and impact contracts.
- Route, location, terrain, era, and score transitions should preserve their
  aggregate invariants under repeated command sequences; property tests should
  cover broad sequence behavior in addition to example tests.

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
- `pyproject.toml` is the dependency metadata source of truth; `requirements-dev.txt`
  is a compatibility shim for tools or workflows that still expect a requirements file.
- `fantasy_simulator/app/` is the headless AppService boundary for future UI
  adapters. Commands and returned view models must stay JSON-serializable plain
  data; UI code may render these payloads, while domain code should continue to
  mutate state through the simulator/world-change APIs.
- `docs/session_handoffs/` is for concise repo-local handoffs; keep entries
  short and factual, anchored to the template, and avoid carrying more than
  the latest relevant dated note.
- Legacy root modules such as `character_domain.py`, `combat.py`,
  `combat_log_index.py`, and `world_*_api.py` are compatibility shims after the
  package split. New code should import from the owning package unless it is
  deliberately preserving a public compatibility path.
- `scripts/quality_gate.py` provides `minimal`, `standard`, `playtest`,
  `strict`, and `exhaustive` verification profiles for agent workflows. The `standard` profile is
  the routine guardrail suite for architecture constraints, quality-gate
  coverage, agent workflow docs, doc freshness, and harness scenarios. The
  `playtest` profile runs deterministic world-health and balance bands. The
  `strict` profile runs the standard guardrail suite, lint, complexity, focused mypy targets,
  and playtest bands without a full-suite pytest pre-pass, so it
  remains suitable for local agent turns with bounded command time. The
  `exhaustive` profile runs static checks plus one full pytest pass for final
  release-style validation. Newly split maintenance packages belong in the
  focused mypy target list once they become owned surfaces, unless
  `scripts/quality_gate.py` records an explicit temporary exclusion reason.
- `scripts/architecture_guard.py` plus `architecture_guard.json` define the
  machine-checkable architecture fitness rules for CI/CD: dependency
  boundaries, headless-domain I/O bans, deterministic reducer imports, and
  acyclic-package rules for inner packages, plus maintainability budgets for
  cyclomatic complexity, cognitive complexity, function length, class size,
  public method count, and first-party fan-out.
  Existing hotspots are recorded as explicit per-target budgets so future work
  cannot quietly make them larger. Relaxed budgets require a reason and are
  reported as stale once a refactor brings the target back under the default
  budget, and typoed or deleted override targets fail as unused debt entries.
  Path globs are depth-aware (`*.py` means direct child, `**/*.py` is
  recursive). Call-boundary rules are lightweight syntax checks over direct AST
  calls; they are fitness functions, not data-flow or alias analysis. Default
  budgets intentionally stay below the current extreme hotspots (`cyclomatic <=
  20`, `cognitive <= 25`, `function lines <= 80`, `public methods <= 12`,
  `class lines <= 220`, `first-party imports <= 12`); anything larger needs a
  named explanation in `architecture_guard.json`.
