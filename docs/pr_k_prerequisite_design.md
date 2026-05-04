# PR-K Prerequisite Design

Status: Phase K0-1 design guardrail
Plan anchor: `docs/implementation_plan.md` Phase I / PR-K
Source: reviewed PR-K prerequisite design, adapted for current `main`

## Purpose

This document records the repo-local design premise for PR-K, dynamic world
change: war, renaming, terrain mutation, era shift, and civilization drift.

It is not a claim that PR-K behavior is fully implemented. It is the guardrail
that later PR-K slices should preserve while adding code, tests, migrations, and
UI/report projections.

PR-K changes more than flavor text. A world change can affect runtime state,
canonical history, reports, atlas/region/detail observations, save/load
compatibility, and setting authoring. K0-1 fixes the language and boundaries
before deeper implementation starts.

## Current Main Premises

The following premises already exist in current `main` and must remain true:

- `World.event_records` is the canonical structured event store.
- `World.event_log` is a compatibility display projection, not the durable
  source of truth.
- `Simulator.history` is a legacy adapter projection from canonical records.
- Locale-aware event display prefers `summary_key` plus JSON-compatible
  `render_params`; `description` remains the compatibility fallback.
- Event visibility can use `location_id`, `location:*` tags, semantic
  `render_params`, and location-targeted impacts.
- Route block/reopen visibility is already a serialization guardrail:
  endpoint IDs and `location:*` tags make both connected locations queryable.
- `docs/serialization_contract.md` is the source for save/load conflict rules.
- `docs/risk_register.md` records the route endpoint/location tag contract and
  remaining serialization risks.
- `SettingBundle` / `WorldDefinition` have authoring places for era, culture,
  faction, language, sites, and routes. Detailed political history and conflict
  state are still PR-K work.

These points should be cited as prerequisites and guardrails, not restated as
new PR-K behavior.

## Design Stack

PR-K should combine a small set of design techniques:

| Technique | Role in PR-K |
|---|---|
| Strategic DDD | Fix shared vocabulary and bounded contexts. |
| Hexagonal architecture | Keep domain logic independent from UI, persistence, and renderers. |
| Event Sourcing lite | Persist important world changes as canonical records while keeping snapshots. |
| CQRS / projection | Separate mutation from observation read models. |
| State machines | Prevent invalid route, rename, war, and era transitions. |
| Functional core | Make validation, transition, event adaptation, reduction, and projection testable. |
| Data-driven rules | Move rule data to `SettingBundle` after the model is stable. |
| Fitness functions | Turn boundaries and event contracts into tests in K0-2 and later slices. |
| ADRs | Record durable decisions before code grows around them. |

The shortest version:

```text
World change is a domain state transition.
It emits canonical history, reduces into runtime state,
and becomes visible through observation projections.
```

## Bounded Contexts

The detailed context map lives in
[`docs/domain/context_map.md`](domain/context_map.md). The K0-1 contexts are:

- World Runtime: current locations, routes, terrain, scores, faction/era state.
- World Change: commands, specifications, state machines, events, reducers.
- Event History: `WorldEventRecord` and compatibility adapters.
- Simulation Timeline: day/month/year advancement and scheduling.
- Observation: reports, atlas, region, detail, story, and rumor projections.
- Narrative / Rumor: memorials, aliases, live traces, rumor/story phrasing.
- Setting Authoring: `SettingBundle` / `WorldDefinition` source data.
- Persistence / Migration: snapshots, schema migration, conflict precedence.
- UI Application: CLI/Rich/Textual orchestration and rendering.
- Worldgen: terrain/site/route generation experiments outside PR-K's mainline.

PR-K should not force a distribution package split before the APIs settle.
Internal module boundaries are enough for the first slices.

## Ubiquitous Language

The shared glossary lives in
[`docs/domain/ubiquitous_language.md`](domain/ubiquitous_language.md).
New PR-K code and tests should prefer those names when possible:

- Command
- Specification
- State Machine
- Domain Event
- WorldEventRecord
- ChangeSet
- Reducer
- Projection
- ViewModel
- Compatibility Adapter

Using the same words in docs, tests, and module names is part of the design
guardrail.

## Event History Policy

PR-K uses Event Sourcing lite, not complete Event Sourcing.

Accepted policy:

- Current world state remains saved as a snapshot.
- Important world changes must be recorded in `World.event_records`.
- `WorldEventRecord` is the canonical source for world history, reports, rumor,
  and observation projections.
- Compatibility buffers can be rebuilt from canonical records.
- Runtime state and event history must not diverge silently.
- Idempotent no-op world-change APIs should not append a new canonical record.
- If canonical recording fails, state mutation must not leave the world half
  changed.

PR-K world-change records should carry semantic data:

```text
id
kind
year / month / day
actor_ids
target_ids
location_id or location_ids
tags
summary_key
render_params
description fallback
cause_event_id optional
compatibility payload optional
```

### Route Block/Reopen Contract

Route block/reopen has an existing contract in
[`docs/serialization_contract.md`](serialization_contract.md):

```text
kind:
  route_blocked / route_reopened

render_params:
  route_id
  from_location_id
  to_location_id
  endpoint_location_ids

tags:
  location:<from_location_id>
  location:<to_location_id>
```

Future PR-K work must preserve both-endpoint visibility and must render from
semantic params, not translated display text.

Later route-mutation slices may add reason metadata such as `reason_key` or
`reason`, but the current serialized contract only requires the semantic route
and endpoint IDs plus location tags.

## State Machine Boundaries

The state machine decision is recorded in
[`docs/adr/0002-pr-k-state-machine-boundaries.md`](adr/0002-pr-k-state-machine-boundaries.md).

PR-K should model at least these transitions:

| Area | Boundary |
|---|---|
| Location naming | `location_id` is stable; official name and aliases are separate. |
| Route mutation | `route_id` and endpoints are stable; blocked/reopened are state/events. |
| War / occupation | faction conflict changes location/faction state and event history. |
| Era / civilization | era and civilization phase affect world-level runtime state and reports. |

Required invariants:

- Rename never changes `LocationState.id`.
- A location has one official display name at a time.
- Previous names remain available as alias/history data.
- Route endpoints always reference existing locations.
- Blocked routes remain queryable from both endpoints.
- Occupied locations and controlling factions must reference known IDs.
- War relationships must not be one-sided by accident.
- Runtime era must reference an authored era definition.
- prosperity, safety, traffic, mood, and similar scores remain in defined ranges.

## Command to Projection Flow

World change should follow this shape:

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
  -> UI / report / rumor / story
```

Reducers should be boring and strict:

- Do not import UI, Rich, Textual, or persistence.
- Do not perform file I/O.
- Do not draw random values.
- Do not invent canonical event records internally.
- Apply a prebuilt `ChangeSet`.
- Leave state in a shape that invariant tests can inspect.

## Observation Read Path

PR-K observation should use projections or view models, not ad hoc UI reads.

Forbidden for new PR-K work:

```text
UI -> World.event_log -> new report
UI -> events_by_type() -> new view model
UI -> raw World internals -> custom world-change display logic
```

Preferred:

```text
World Runtime + Event History
  -> Projection
  -> ViewModel
  -> CLI / Rich / future Textual renderer
```

Projection candidates:

| Projection | Purpose |
|---|---|
| LocationHistoryProjection | rename, aliases, occupation, memorials, recent events. |
| RouteStatusProjection | open/blocked/contested/repairing state and route history. |
| WarMapProjection | conflicts, occupied sites, front/affected regions. |
| EraTimelineProjection | era shift and civilization phase history. |
| RegionChangeProjection | local recent changes for atlas/region/detail views. |
| WorldChangeReportProjection | monthly/yearly world-change summaries. |

## Testing And Fitness Plan

K0-1 records design. Current main has now started the K0 executable guardrail
slices for route block/reopen, location rename, occupation/control, and
terrain-cell mutation:

- `fantasy_simulator/world_change/` contains the first command, state machine,
  event adapter, ChangeSet, and reducer paths for route block/reopen,
  location rename, location occupation/control, and headless era/civilization
  transitions. Terrain-cell mutation is wired through command, specification,
  transition, domain event, event adapter, ChangeSet, reducer, and
  `World.apply_terrain_cell_change`.
- `fantasy_simulator/observation/` contains route status, location history,
  war/occupation, era timeline, and world-change report read models, including
  the terrain-change report category.
- PR-K architecture, event contract, state-machine, projection, and save
  contract tests are part of the standard quality-gate target list, including
  the terrain mutation state-machine target.
- Save schema remains v8 for these slices because route state, location
  aliases, controlling faction state, terrain mutation snapshots, and canonical
  event records already have durable fields. Bundle-backed worlds omit derived
  terrain unless runtime terrain cells change, then persist a complete
  `terrain_map` snapshot that load validates before overlaying on
  bundle-derived topology. World-level era runtime remains
  pre-persistence/headless until its save policy is settled.

Remaining K0 phases should continue in this order:

| Phase | Focus |
|---|---|
| K0-2 | architecture boundaries, event contracts, legacy-read policy, invariants. |
| K0-3 | seeded characterization and report/map golden masters. |
| K0-4 | typed ID ratchet for location, route, faction, event, era, culture. |
| K0-5 | minimal route block/reopen slice through command, reducer, projection. Started. |
| K0-6 | location rename slice and rename history invariants. Started. |
| K0-6b | location occupation/control slice and war-map projection. Started. |
| K0-6c | headless era/civilization transition core and timeline projection. Started, not persisted as runtime fields. |
| K0-7 | save/migration policy for PR-K dynamic fields. v8 terrain policy set; era runtime pending. |

Fitness functions should eventually guard:

- `world_change` does not import UI, renderers, or persistence.
- observation/projection modules do not mutate world state.
- new report, rumor, presenter, and view-model paths read canonical records or
  projections.
- legacy `event_log` and `events_by_type()` reads do not expand into new PR-K
  primary paths.
- route records keep endpoint IDs and `location:*` tags.
- rename records keep old name, new name, and `location_id`.
- war/occupation records keep faction IDs and affected location IDs.
- terrain mutation records keep cell coordinates, `terrain_cell_id`, changed
  attributes, old/new terrain values, optional `location_id`, and semantic
  impacts.
- save/load roundtrip preserves runtime state and canonical event history.

### Terrain Cell Mutation Contract

Terrain-cell mutation is a PR-K world-change slice, not a terrain generator
rewrite. A successful mutation must:

- validate the target cell exists inside the active `TerrainMap`;
- normalize requested `biome`, `elevation`, `moisture`, and `temperature`;
- no-op without a record when no terrain attribute changes;
- emit one canonical `WorldEventRecord` with kind `terrain_cell_mutated`;
- reduce the prepared runtime update into `TerrainMap.set_cell()` or an
  equivalent full-cell replacement;
- keep persistence at schema v8 by relying on the complete `terrain_map`
  snapshot policy for mutated bundle-backed terrain.

Required semantic record data:

```text
kind:
  terrain_cell_mutated

render_params:
  terrain_cell_id
  x
  y
  old_biome / new_biome
  old_elevation / new_elevation
  old_moisture / new_moisture
  old_temperature / new_temperature
  changed_attributes
  location_id optional
  reason_key optional
  cause_event_id optional

tags:
  world_change
  terrain
  terrain_cell:<x>:<y>
  location:<location_id> optional

impacts:
  target_type: terrain_cell
  target_id: terrain:<x>:<y>
  attribute: each changed terrain attribute
  old_value / new_value
```

Display labels such as biome names may be rendered later by projections or
i18n. The durable record stores semantic values and IDs, not translated
surface text.

## Minimum PR-K Slice Template

Each PR-K implementation slice should use this checklist:

1. Update the relevant ADR/design note if the decision changes.
2. Define a command.
3. Define the specification/validation rule.
4. Define the state transition.
5. Define the domain event.
6. Adapt the domain event to `WorldEventRecord`.
7. Build a `ChangeSet`.
8. Reduce the `ChangeSet` into runtime state.
9. Build projection/view-model output.
10. Connect report, atlas, region, or detail display.
11. Add contract, invariant, characterization, and migration tests as needed.
12. Run the appropriate quality gate.

## Deferred Ideas

These are intentionally out of scope for PR-K prerequisites:

- complete Event Sourcing replay for all state
- ECS as the primary model
- full agent-based or utility-AI faction decisions
- full Textual migration
- microservice or distribution package split
- a large external rule DSL before the domain model stabilizes

## Documents To Synchronize Later

When PR-K code lands, keep these documents aligned:

- `docs/implementation_plan.md`: PR-K completion status and next slice.
- `docs/serialization_contract.md`: any new serialized field or conflict rule.
- `docs/risk_register.md`: newly closed or opened PR-K risks.
- `docs/architecture.md`: new enforced module boundaries.
- README: only after behavior is actually implemented and user-visible.
