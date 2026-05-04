# PR-K Context Map

Status: Phase K0-1 design guardrail
Scope: PR-K dynamic world change

This context map records how PR-K concepts should relate before production
implementation begins. It extends the current architecture guardrails without
replacing `docs/architecture.md`.

## Contexts

| Context | Responsibility | PR-K role |
|---|---|---|
| Setting Authoring | Defines `SettingBundle` / `WorldDefinition` data. | Provides era, faction, naming, and rules. |
| World Runtime | Holds locations, terrain, routes, scores, factions, era. | Receives validated reductions. |
| World Change | Owns commands, state machines, events, changesets, reducers. | Main PR-K domain boundary. |
| Event History | Owns canonical `WorldEventRecord` and adapters. | Makes changes durable and queryable. |
| Simulation Timeline | Advances time and schedules possible commands. | Initiates changes without owning rules. |
| Observation | Builds projections and view models. | Reads changes without mutating state. |
| Narrative / Rumor | Turns history and memory into rumor/story text. | Consumes projections and records. |
| Persistence / Migration | Saves snapshots and migrates older data. | Preserves compatibility. |
| UI Application | Handles CLI/Rich/future Textual orchestration. | Renders view models. |
| Worldgen | Experiments with terrain/site/route shapes. | Adjacent to PR-K mainline. |

## High-Level Flow

```text
Setting Authoring
  -> World Runtime initialization
  -> World Change rule data

Simulation Timeline / UI Application
  -> World Change commands

World Change
  -> validates commands
  -> performs state transitions
  -> emits domain events
  -> adapts canonical WorldEventRecords
  -> reduces ChangeSets into World Runtime

Event History
  -> stores canonical records
  -> provides compatibility adapters

World Runtime + Event History
  -> Observation projections
  -> ViewModels
  -> UI / report / rumor / story rendering

Persistence / Migration
  -> snapshots World Runtime + Event History
  -> migrates older snapshots into canonical shape
```

## Dependency Direction

The intended dependency direction is inward:

```text
UI / Renderer / Persistence / Bundle Loader
        ↓
Application Service / Composition Root
        ↓
World Change / Simulation / Event History / World Runtime
        ↓
Core value objects / contracts
```

World Change code should stay headless and deterministic. UI, renderers,
persistence, concrete bundle loading, and developer tools are adapters.

## Allowed Relationships

- Simulation Timeline may create or dispatch world-change commands.
- UI Application may dispatch commands through an application/composition layer.
- World Change may read World Runtime and Setting Authoring data through narrow
  inputs or ports.
- World Change may emit domain events and canonical records.
- Reducers may apply prepared `ChangeSet` values to World Runtime.
- Observation may read World Runtime and Event History.
- UI/renderers may read ViewModels.
- Persistence may snapshot World Runtime and Event History.
- Compatibility adapters may project canonical records for old APIs.

## Forbidden Relationships

- World Change must not import CLI, Rich, Textual, or UI renderers.
- World Change must not call save/load directly.
- World Change reducers must not draw random numbers.
- Observation must not mutate World Runtime.
- UI must not create new PR-K reports by directly reading `World.event_log`.
- UI must not use `events_by_type()` as a new primary read path.
- Persistence must not import UI.
- Compatibility adapters must not become the primary path for new PR-K features.
- Worldgen experiments must not become required runtime dependencies for PR-K
  state transitions.

## Ports And Adapters

Candidate ports for later slices:

| Port | Purpose |
|---|---|
| EventRecorderPort | Append canonical `WorldEventRecord` values. |
| WorldMutationPort | Apply validated state patches. |
| RandomSource | Provide deterministic random inputs outside domain reducers. |
| BundleProvider | Provide `SettingBundle` / `WorldDefinition` data. |
| SnapshotPort | Hide save/load implementation details. |
| ProjectionQuery | Fetch read models for observation surfaces. |

Candidate adapters:

- persistence adapter
- CLI input adapter
- Rich renderer
- future Textual app
- SettingBundle JSON loader
- compatibility event-log/history adapter
- worldgen PoC bridge

## Candidate Module Shape

Do not treat this as a required package split for K0-1. It is a naming sketch
for later PR-K slices if the implementation needs it:

```text
fantasy_simulator/world_change/
  commands.py
  specifications.py
  state_machines.py
  domain_events.py
  event_adapters.py
  changesets.py
  reducers.py
  invariants.py

fantasy_simulator/observation/
  location_history_projection.py
  route_status_projection.py
  war_map_projection.py
  era_timeline_projection.py
  world_change_report_projection.py
```

Existing modules such as `reports.py`, `rumor.py`, `ui/view_models.py`, and
`ui/presenters.py` may remain integration points while boundaries settle.

## C4-Lite Summary

Context:

```text
Player
  -> Fantasy Simulator
  -> save data
  -> setting bundle
```

Container:

```text
Engine / Simulation
Persistence
UI / Renderer
Content / Setting Bundle
Worldgen tools
```

Component:

```text
World Change
Event History
World Runtime
Observation
Simulation Timeline
```

Code-level design targets:

```text
command
specification
state machine
domain event
event adapter
changeset
reducer
projection
```
