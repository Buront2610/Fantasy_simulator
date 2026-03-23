# Fantasy Simulator

A Python CLI world and life simulation set in the fantasy world of Aethoria.

This project is not a separate RPG battle loop. Characters live inside the same
world simulation, form relationships, travel, age, fight, discover things, and
can now take part in multi-step adventures that the player can inspect and
occasionally influence.

## Features

- Yearly time progression in the CLI, with monthly simulation/report foundations under development
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
python main.py
```

The repository does not yet use the planned package entry point by default. The
current roadmap for package migration, true monthly progression, UI separation,
and later phase features is maintained in
[`docs/implementation_plan.md`](docs/implementation_plan.md).

Run tests:

```bash
python -m pytest
```

## Project Structure

- `character.py`: core character model
- `character_creator.py`: random, template, and interactive character creation
- `world.py`: world state, locations, map, and world serialization
- `events.py`: event generation and event resolution
- `adventure.py`: multi-step adventure progression
- `simulator.py`: current simulation orchestration
- `reports.py`: monthly and yearly report view generation
- `rumor.py`: rumor generation and lifecycle helpers
- `migrations.py`: schema migration helpers for save compatibility
- `save_load.py`: snapshot save/load helpers
- `main.py`: CLI interface
- `docs/implementation_plan.md`: current implementation roadmap and phase order
- `docs/next_version_plan.md`: long-range design target
- `docs/ui_renovation_plan.md`: UI renovation strategy
- `tests/`: automated tests

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

- Establish documentation source-of-truth and keep the README aligned with it
- Move toward package-based structure and clearer module boundaries
- Complete true monthly progression and deterministic monthly test coverage
- Normalize `World.event_records` as the canonical event store
- Separate UI/presentation concerns before expanding party adventure and AA map features
