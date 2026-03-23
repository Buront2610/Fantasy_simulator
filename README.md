# Fantasy Simulator

A Python CLI world and life simulation set in the fantasy world of Aethoria.

This project is not a separate RPG battle loop. Characters live inside the same
world simulation, form relationships, travel, age, fight, discover things, and
can now take part in multi-step adventures that the player can inspect and
occasionally influence.

## Features

- Yearly time progression in the CLI, with monthly reports, rumors, and event-record foundations implemented but true monthly progression not yet complete
- Character generation with random and template-based creation
- Event system for meetings, journeys, discoveries, training, battles, aging,
  marriage, and natural death
- World map and character roster views
- Character story output and simulation summary output
- Integrated adventure runs with:
  - summary logs
  - detailed logs
  - pending player choices
  - automatic default resolution when choices are left unresolved
- Save/load support for simulation snapshots
- Schema-versioned save migration support for older data
- Structured world event records, rumors, and monthly/yearly reports
- CLI localization support for Japanese and English

## Running

Requirements:

- Python 3.10+

Start the CLI:

```bash
python -m fantasy_simulator
```

Or using the legacy entry point:

```bash
python main.py
```

The codebase has been migrated to a `fantasy_simulator/` package layout. The
current roadmap for true monthly progression, simulator refactoring, UI
separation, and later phase features is maintained in
[`docs/implementation_plan.md`](docs/implementation_plan.md).

Run tests:

```bash
python -m pytest
```

## Project Structure

```
fantasy_simulator/          # Main package
  __init__.py
  __main__.py               # python -m fantasy_simulator entry point
  main.py                   # CLI logic
  character.py              # Core character model
  character_creator.py      # Random, template, and interactive character creation
  world.py                  # World state, locations, map, and world serialization
  events.py                 # Event generation and resolution
  adventure.py              # Multi-step adventure progression
  simulator.py              # Simulation orchestration
  reports.py                # Monthly and yearly report view generation
  rumor.py                  # Rumor generation and lifecycle helpers
  persistence/
    save_load.py            # Snapshot save/load helpers
    migrations.py           # Schema migration for save compatibility
  ui/
    screens.py              # CLI screen and menu functions
    ui_helpers.py           # Display formatting and input utilities
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
  next_version_plan.md      # Long-range design target
  ui_renovation_plan.md     # UI renovation strategy
```

## Design Direction

- Adventures remain inside the main simulation instead of becoming a separate
  game mode.
- Player control is selective intervention at important moments.
- The same adventure supports normal summary viewing, deeper inspection, and
  rare player choice points.
- Changes are being kept incremental and modular.

## Current Limitations

- Event causality is still fairly lightweight and can be deepened further.
- Some generated event text is still English-first even when the CLI language is
  set to Japanese.
- The simulation is tuned for readability and experimentation rather than
  perfect realism.

## Near-Term Priorities

- Complete true monthly progression and deterministic monthly test coverage
- Split `simulator.py` responsibilities and normalize `World.event_records` as the canonical event store
- Separate UI/presentation concerns before expanding party adventure and AA map features
- Maintain documentation source-of-truth alignment as the roadmap evolves
