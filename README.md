# Fantasy Simulator

A Python CLI world and life simulation set in the fantasy world of Aethoria.

This project is not a separate RPG battle loop. Characters live inside the same
world simulation, form relationships, travel, age, fight, discover things, and
take part in multi-step adventures that the player can inspect and occasionally
influence.

## Features

- Yearly CLI progression backed by a monthly-resolution simulation engine
- Character generation with random and template-based creation
- Event system for meetings, journeys, discoveries, training, battles, aging,
  marriage, and natural death
- Character roster, story output, simulation summaries, and structured event logs
- Auto-advance until meaningful pause conditions are met
- Monthly and yearly reports derived from structured event records
- World memory features:
  - live traces
  - memorials
  - location aliases
- Integrated adventure runs with:
  - summary logs
  - detailed logs
  - pending player choices
  - automatic default resolution when choices are left unresolved
- Terrain/site/route world representation with:
  - variable world dimensions
  - ASCII grid rendering
  - atlas overview rendering
  - region drill-down
  - location detail panels
- Save/load support for simulation snapshots
- Schema-versioned save migration support for older data (`schema_version = 7`)
- Structured world event records with causal impact tracking and rumors
- UI abstraction through input/render backends plus lightweight presenter/view-model layers
- CLI localization support for Japanese and English

## Running

Requirements:

- Python 3.10+
- Optional UI extras:
  - `rich` (thin Rich render shell)
  - `prompt_toolkit` (input assistance backend)

Start the CLI:

```bash
python -m fantasy_simulator
```

Optional backend selection (explicit opt-in):

```bash
# default: StdInputBackend + PrintRenderBackend
export FANTASY_SIMULATOR_INPUT_BACKEND=prompt_toolkit
export FANTASY_SIMULATOR_UI_BACKEND=rich
python -m fantasy_simulator
```

Or using the legacy entry point:

```bash
python main.py
```

The codebase uses a `fantasy_simulator/` package layout with a `simulation/`
sub-package for separated concerns (engine, timeline, notifications, event
recording, adventure coordination, and query/reporting). The UI layer is
abstracted through `InputBackend` / `RenderBackend` protocols, a `UIContext`
dependency container, renderer modules, and presenter/view-model helpers. The
current roadmap is maintained in
[`docs/implementation_plan.md`](docs/implementation_plan.md), and the current
repo-level guardrails are summarized in
[`docs/architecture.md`](docs/architecture.md).

**Compatibility note (PR-A):** CLI launch (`python -m fantasy_simulator` and
`python main.py`) and save/load compatibility are preserved. However, old
bare-module imports such as `from i18n import tr` or `from world import World`
are **no longer supported**. All imports must now use the package path, e.g.
`from fantasy_simulator.i18n import tr`,
`from fantasy_simulator.world import World`.

Run tests:

```bash
python -m pytest
```

Agent-oriented verification profiles:

```bash
python scripts/quality_gate.py minimal --pytest-target tests/test_character_creator.py
python scripts/quality_gate.py standard
python scripts/quality_gate.py strict
```

Minimal role-based orchestration (planner -> implementer -> verifier -> reviewer):

```bash
python scripts/agent_orchestrator.py "Add bounded orchestration contract" \
  --plan-anchor PR-I-orchestrator \
  --changed-file scripts/agent_orchestrator.py \
  --changed-file tests/test_agent_orchestrator.py
```

Run artifacts are persisted as `.runs/<task-id>/manifest.json` for machine-readable workflow traces.

`minimal` is intentionally explicit: pass one or more `--pytest-target` values
for the changed area you want to verify.

`standard` is the repo's day-to-day guardrail profile. It exercises the
architecture constraints, the quality-gate self-test, the agent workflow docs
checks, doc freshness, and the harness scenario suite.

## Project Structure

```
fantasy_simulator/          # Main package
  __init__.py
  __main__.py               # python -m fantasy_simulator entry point
  main.py                   # CLI logic
  character.py              # Core character model
  character_creator.py      # Random, template, and interactive character creation
  world.py                  # World state, locations, memory, terrain hooks, serialization
  terrain.py                # Terrain / site / route / atlas layout models
  events.py                 # Event generation, EventResult, WorldEventRecord
  adventure.py              # Multi-step adventure progression
  simulator.py              # Backward-compatible import path (delegates to simulation/)
  reports.py                # Monthly and yearly report view generation
  rumor.py                  # Rumor generation and lifecycle helpers
  simulation/               # Simulator split into single-responsibility modules
    __init__.py             # Re-exports Simulator
    engine.py               # Core Simulator class (orchestration, loops, serialization)
    timeline.py             # Monthly processing, seasonal modifiers, dying/injury
    notifications.py        # Notification threshold evaluation
    event_recorder.py       # Event recording across all event stores
    adventure_coordinator.py # Adventure lifecycle management
    queries.py              # Summary, report, story, and event-log access
  persistence/
    save_load.py            # Snapshot save/load helpers
    migrations.py           # Schema migration for save compatibility
  ui/
    screens.py              # CLI screen and menu functions
    ui_helpers.py           # Display formatting and input utilities
    ui_context.py           # UIContext dependency container (InputBackend + RenderBackend)
    presenters.py           # Screen-friendly formatting helpers
    view_models.py          # UI-facing view models from canonical data
    map_renderer.py         # Map data extraction (MapCellInfo/MapRenderInfo) and ASCII rendering
    atlas_renderer.py       # Atlas-scale overview rendering
    input_backend.py        # InputBackend protocol + Std / PromptToolkit backends
    render_backend.py       # RenderBackend protocol + Print / Rich backends
  narrative/
    context.py              # Minimal NarrativeContext helpers for memorials / aliases
    template_history.py     # Template cooldown / selection helper
  content/
    world_data.py           # Races, jobs, locations, skills, lore definitions
  i18n/
    engine.py               # Localization helpers (tr, tr_term, set_locale)
    ja.py                   # Japanese text and terms
    en.py                   # English text and terms
main.py                     # Compatibility wrapper (delegates to package)
tests/                      # Automated tests
docs/
  implementation_plan.md    # Implementation roadmap and phase order
  architecture.md           # Current architectural guardrails and canonical data rules
  contexts/                 # Short task-mode context docs for implementation/review
  session_handoffs/         # Template + latest repo-local handoff notes
  subagent_contract.md      # Delegation format for subagent tasks
  agent_lessons.md          # Curated recurring agent workflow lessons
  next_version_plan.md      # Long-range design target
  ui_renovation_plan.md     # UI renovation strategy
scripts/
  quality_gate.py           # minimal|standard|strict verification runner
  quality_gate.ps1          # Thin PowerShell wrapper for the quality gate
```

## CLI Flow

Current main menu:

- Start new simulation
- Create custom simulation
- Load saved simulation
- Read world lore
- Change language
- Exit

After a simulation starts or is loaded, the post-simulation menu currently
supports:

- advancing by 1 year / 5 years / auto-pause
- yearly and monthly reports
- atlas/world map browsing
- character roster and stories
- recent/full event log viewing
- adventure summaries, detail inspection, and pending-choice resolution
- save snapshots
- location history browsing

## Design Direction

- Adventures remain inside the main simulation instead of becoming a separate
  game mode.
- Player control is selective intervention at important moments.
- The same adventure supports normal summary viewing, deeper inspection, and
  rare player choice points.
- The world model is being expanded incrementally through terrain/site/route
  separation and atlas-scale observation UI.
- Changes are being kept incremental and modular.

## Current Limitations

- Some generated event text is still English-first even when the CLI language is
  set to Japanese.
- Terrain generation is still deterministic scaffolding from the current site
  grid, not a full worldgen pipeline.
- NarrativeContext is still minimal and currently focused on memorial / alias
  text selection.
- The base world setting is still largely hard-coded in
  `content/world_data.py`; it is not yet loaded as an external setting bundle.
- The simulation is tuned for readability and experimentation rather than
  perfect realism.

## Near-Term Priorities

- Continue PR-I after the first `NarrativeContext` slice that now feeds relation
  tags, yearly reports, and location memory into memorial / alias text selection
- Continue world setting externalization work toward the first formal
  `SettingBundle` authoring pass (PR-J)
- Treat worldgen PoC work as parallel technical validation, not the next
  blocking mainline milestone

For the full roadmap (NarrativeContext, SettingBundle, worldbuilding, dynamic
world changes, etc.), see `docs/implementation_plan.md`.
