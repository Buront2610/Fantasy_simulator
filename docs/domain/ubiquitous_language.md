# PR-K Ubiquitous Language

Status: Phase K0-1 design guardrail
Scope: PR-K dynamic world change

This glossary fixes the words used by PR-K docs, tests, and future module names.
It describes intended boundaries and contracts. It does not claim that every
term already has a production implementation.

## Core Terms

| Term | Meaning |
|---|---|
| World Runtime | Current mutable world state: locations, routes, terrain, scores, factions, era. |
| World Change | A meaningful state change: route closure, rename, war, occupation, era shift. |
| Domain Event | A domain fact emitted by world-change logic, before or while being adapted into a canonical record. |
| WorldEventRecord | The canonical serialized record for event history, reporting, rumor, and observation projections. |
| Event History | The durable world history centered on `World.event_records`. |
| Command | A request to change world state, for example `BlockRouteCommand` or `RenameLocationCommand`. |
| Specification | A validation rule that decides whether a command is currently allowed. |
| State Machine | The explicit transition model for route, location name, war/occupation, or era state. |
| Reducer | The deterministic application of a prepared `ChangeSet` into World Runtime state. |
| ChangeSet | The result of a command: canonical events plus runtime updates and projection hints. |
| Projection | A read model built from World Runtime and Event History for reports, maps, story, or rumor. |
| ViewModel | UI-independent data shaped for a renderer or report formatter. |
| Compatibility Adapter | A boundary for legacy surfaces such as `event_log`, `history`, or `events_by_type()`. |
| Observation | A read path that explains world state: report, atlas, detail, rumor, or story. |
| Setting Authoring | `SettingBundle` / `WorldDefinition` data for era, culture, faction, naming, and rules. |

## Event And Record Terms

| Term | Meaning |
|---|---|
| Canonical Event Store | `World.event_records`, the authoritative durable event source. |
| Compatibility Display Buffer | `World.event_log`, a display projection retained for older paths. |
| Legacy History Adapter | `Simulator.history`, a compatibility projection for older `EventResult` consumers. |
| Summary Key | Locale-aware rendering key stored on `WorldEventRecord`. |
| Render Params | JSON-compatible semantic values used with `summary_key`; IDs stay IDs. |
| Description Fallback | Compatibility text used when structured rendering is unavailable. |
| Cause Event | Optional event ID linking a world change to its triggering event. |
| Location Tag | A tag such as `location:town_harbor` used to make records visible from related locations. |
| Endpoint Visibility | Route events are queryable from both endpoints through IDs and `location:*` tags. |

## World Runtime Terms

| Term | Meaning |
|---|---|
| Location ID | Stable identity for a location. It must not change when the location is renamed. |
| Official Name | The current canonical display name; one official name per location. |
| Alias | An alternate or historical name kept for memory, rumor, or narrative display. |
| Rename History | The ordered record of official name changes and old-name preservation. |
| Route ID | Stable identity for a route edge. Block/reopen does not replace it. |
| Route Endpoint | One of the two location IDs connected by a route. Endpoints must remain valid. |
| Route Status | Runtime state such as open, blocked, contested, or repairing. |
| Terrain Cell | One coordinate in the active `TerrainMap`, identified by `x` and `y`. |
| Terrain Cell ID | Semantic event ID for a cell, currently `terrain:<x>:<y>`. |
| Terrain Cell Mutation | A runtime terrain change that updates cell biome or scalar terrain values. |
| Controlling Faction | The faction currently controlling a location, when faction state exists. |
| Occupation | A location/faction state in which control changed through conflict or force. |
| Era Key | Stable key for the current authored era definition. |
| Civilization Phase | Runtime phase such as stable, crisis, transition, new era, or aftermath. |
| World Score | Bounded numeric state such as prosperity, safety, traffic, or mood. |

## Process Terms

| Term | Meaning |
|---|---|
| Functional Core | Mostly pure validation, transition, event creation, reducer, projection, and invariants. |
| Imperative Shell | CLI input, renderer orchestration, save/load I/O, seed setup, and command dispatch. |
| Fitness Function | A test or script that enforces a design boundary or event contract. |
| Characterization Test | A fixed-seed or golden-master test that protects existing behavior during refactor. |
| Contract Test | A test that fixes required event metadata, queryability, or serialization behavior. |
| Invariant Test | A test that checks world consistency after one or more changes. |
| Migration Policy | The rule for preserving older saves when new PR-K runtime fields are introduced. |

## Naming Guidance

Prefer these words in future PR-K modules and tests:

- `commands`
- `specifications`
- `state_machines`
- `domain_events`
- `event_adapters`
- `changesets`
- `reducers`
- `invariants`
- `projections`
- `view_models`

Avoid using compatibility terms as primary-path names for new PR-K behavior.
For example, a new projection should not be named around `event_log` or
`events_by_type()`.
