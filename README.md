# Fantasy Simulator

A Python CLI world and life simulation set in the fantasy world of Aethoria.

This project is not a separate RPG battle loop. Characters live inside the same
world simulation, form relationships, travel, age, fight, discover things, and
can now take part in multi-step adventures that the player can inspect and
occasionally influence.

## Features

- World simulation with yearly time progression
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
- CLI localization support for Japanese and English

## Running

Requirements:

- Python 3.10+

Start the CLI:

```bash
python main.py
```

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
- `simulator.py`: yearly simulation orchestration
- `save_load.py`: snapshot save/load helpers
- `main.py`: CLI interface
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

- Deepen relationship and social causality
- Improve adventure consequence modeling
- Expand world and creator test coverage
- Localize more generated narrative text
