"""
main.py - Entry point for the Fantasy Simulator CLI.

Run with: python main.py
"""

from __future__ import annotations

import sys
import textwrap
from typing import List, Optional

from character import Character
from character_creator import CharacterCreator
from save_load import load_simulation, save_simulation
from simulator import Simulator
from world import World
from world_data import WORLD_LORE


# ---------------------------------------------------------------------------
# ANSI colour helpers (no external deps)
# ---------------------------------------------------------------------------

def _c(text: str, code: str) -> str:
    """Wrap text in an ANSI colour/style code (reset after)."""
    return f"\033[{code}m{text}\033[0m"

def bold(t: str)    -> str: return _c(t, "1")
def red(t: str)     -> str: return _c(t, "31")
def green(t: str)   -> str: return _c(t, "32")
def yellow(t: str)  -> str: return _c(t, "33")
def cyan(t: str)    -> str: return _c(t, "36")
def magenta(t: str) -> str: return _c(t, "35")
def blue(t: str)    -> str: return _c(t, "34")
def dim(t: str)     -> str: return _c(t, "2")


# ---------------------------------------------------------------------------
# ASCII art header
# ---------------------------------------------------------------------------

HEADER = r"""
  ╔══════════════════════════════════════════════════════════════╗
  ║                                                              ║
  ║    █████╗ ███████╗████████╗██╗  ██╗ ██████╗ ██████╗ ██╗ █╗  ║
  ║   ██╔══██╗██╔════╝╚══██╔══╝██║  ██║██╔═══██╗██╔══██╗██║ ██║  ║
  ║   ███████║█████╗     ██║   ███████║██║   ██║██████╔╝██║ ██║  ║
  ║   ██╔══██║██╔══╝     ██║   ██╔══██║██║   ██║██╔══██╗██║ ██║  ║
  ║   ██║  ██║███████╗   ██║   ██║  ██║╚██████╔╝██║  ██║██║ ██║  ║
  ║                                                              ║
  ║        ✦  W O R L D   S I M U L A T O R  ✦                  ║
  ║                   ── A E T H O R I A ──                      ║
  ╚══════════════════════════════════════════════════════════════╝
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hr(char: str = "─", width: int = 62) -> str:
    return "  " + char * width


def _pause() -> None:
    input(dim("\n  [Press ENTER to continue] "))


def _print_wrapped(text: str, indent: int = 4) -> None:
    prefix = " " * indent
    for line in text.splitlines():
        if line.strip():
            for wrapped in textwrap.wrap(line, width=70, initial_indent=prefix,
                                         subsequent_indent=prefix):
                print(wrapped)
        else:
            print()


def _choose(prompt: str, options: List[str], default: Optional[str] = None) -> str:
    """Simple numbered-choice prompt. Returns chosen option string."""
    print()
    for i, opt in enumerate(options, 1):
        marker = green("►") if str(i) == default else " "
        print(f"  {marker} {cyan(str(i))}.  {opt}")
    print()
    while True:
        hint = f" (default {default})" if default else ""
        raw = input(f"  {bold('Your choice')}{hint}: ").strip()
        if not raw and default:
            raw = default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print(red("  Invalid choice. Please enter a number."))


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

def _build_default_world(num_characters: int = 12) -> World:
    """Create a fresh World with random adventurers."""
    world = World()
    creator = CharacterCreator()
    locations = [loc.name for loc in world.grid.values() if loc.region_type != "dungeon"]

    import random
    for _ in range(num_characters):
        char = creator.create_random()
        char.location = random.choice(locations)
        world.add_character(char)

    return world


def _run_simulation(world: World, years: int) -> Simulator:
    """Run the simulation and return the Simulator with full history."""
    print()
    print(f"  {bold('Running simulation...')} ({years} years × ~8 events/year)")
    sim = Simulator(world, events_per_year=8)
    for y in range(years):
        sim._run_year()
        alive = sum(1 for c in world.characters if c.alive)
        bar_len = 30
        filled = int(bar_len * (y + 1) / years)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(
            f"  [{bar}] Year {world.year}  |  "
            f"{green(str(alive))} alive",
            end="\r",
        )
    print()
    print(f"  {green('✓')}  Simulation complete.")
    return sim


def _show_results(sim: Simulator) -> None:
    """Interactive results viewer after simulation finishes."""
    world = sim.world

    while True:
        print("\n" + _hr("═"))
        print(bold("  POST-SIMULATION RESULTS"))
        print(_hr("═"))
        action = _choose(
            "What would you like to see?",
            [
                "World map",
                "Character roster",
                "Event log (last 30)",
                "Full event log",
                "Adventure summaries",
                "Adventure details",
                "Resolve pending adventure choice",
                "Save simulation snapshot",
                "Character story (choose one)",
                "All character stories",
                "Simulation summary",
                "Back to main menu",
            ],
        )

        if action == "World map":
            print()
            print(world.render_map())
            _pause()

        elif action == "Character roster":
            _show_roster(world)

        elif action == "Event log (last 30)":
            print()
            for entry in sim.get_event_log(last_n=30):
                print(f"  {dim('•')} {entry}")
            _pause()

        elif action == "Full event log":
            print()
            for entry in sim.get_event_log():
                print(f"  {dim('•')} {entry}")
            _pause()

        elif action == "Adventure summaries":
            _show_adventure_summaries(sim)

        elif action == "Adventure details":
            _show_adventure_details(sim)

        elif action == "Resolve pending adventure choice":
            _resolve_pending_adventure_choice(sim)

        elif action == "Save simulation snapshot":
            _save_simulation_snapshot(sim)

        elif action == "Character story (choose one)":
            _show_single_story(sim)

        elif action == "All character stories":
            print()
            print(sim.get_all_stories())
            _pause()

        elif action == "Simulation summary":
            print()
            print(sim.get_summary())
            _pause()

        else:
            break


def _show_roster(world: World) -> None:
    """Display every character's basic stats in a table."""
    print()
    print(_hr())
    header = (
        f"  {'Name':<22} {'Race/Job':<22} {'Age':>4}  "
        f"{'STR':>4}{'INT':>4}{'DEX':>4}  {'Status':<10}  Location"
    )
    print(bold(header))
    print(_hr())
    for c in world.characters:
        status = green("Alive") if c.alive else red("Dead ")
        name_trunc = c.name[:21]
        racejob = f"{c.race} {c.job}"[:21]
        loc_trunc = c.location[:20]
        print(
            f"  {name_trunc:<22} {racejob:<22} {c.age:>4}  "
            f"{c.strength:>4}{c.intelligence:>4}{c.dexterity:>4}  "
            f"{status}  {loc_trunc}"
        )
    print(_hr())
    _pause()


def _show_single_story(sim: Simulator) -> None:
    """Let the user pick a character and show their story."""
    world = sim.world
    print()
    for i, c in enumerate(world.characters, 1):
        status = green("✓") if c.alive else red("✗")
        print(f"  {i:>2}. [{status}] {c.name} ({c.race} {c.job}, age {c.age})")
    print()
    raw = input("  Enter character number (or ENTER to cancel): ").strip()
    if not raw or not raw.isdigit():
        return
    idx = int(raw) - 1
    if 0 <= idx < len(world.characters):
        char = world.characters[idx]
        print()
        print(sim.get_character_story(char.char_id))
        _pause()


def _show_adventure_summaries(sim: Simulator) -> None:
    """Display known adventures in compact summary form."""
    runs = list(sim.world.completed_adventures) + list(sim.world.active_adventures)
    print()
    if not runs:
        print(dim("  No adventures have been recorded."))
        _pause()
        return

    print(_hr())
    print(bold("  ADVENTURE SUMMARIES"))
    print(_hr())
    for i, run in enumerate(runs, 1):
        status = run.outcome or run.state
        loot = f" | loot: {', '.join(run.loot_summary)}" if run.loot_summary else ""
        injury = f" | injury: {run.injury_status}" if run.injury_status != "none" else ""
        print(
            f"  {i:>2}. {run.character_name} | {run.origin} -> {run.destination} "
            f"| {status}{injury}{loot}"
        )
    print(_hr())
    _pause()


def _show_adventure_details(sim: Simulator) -> None:
    """Let the user inspect a single adventure's detailed log."""
    runs = list(sim.world.completed_adventures) + list(sim.world.active_adventures)
    print()
    if not runs:
        print(dim("  No adventures are available to inspect."))
        _pause()
        return

    for i, run in enumerate(runs, 1):
        status = run.outcome or run.state
        print(f"  {i:>2}. {run.character_name} at {run.destination} [{status}]")
    print()
    raw = input("  Enter adventure number (or ENTER to cancel): ").strip()
    if not raw or not raw.isdigit():
        return

    idx = int(raw) - 1
    if not (0 <= idx < len(runs)):
        return

    run = runs[idx]
    print()
    print(_hr())
    print(bold(f"  ADVENTURE DETAIL - {run.character_name}"))
    print(_hr())
    print(f"  ID          : {run.adventure_id}")
    print(f"  Route       : {run.origin} -> {run.destination}")
    print(f"  State       : {run.state}")
    print(f"  Outcome     : {run.outcome or 'unresolved'}")
    print(f"  Injury      : {run.injury_status}")
    print(f"  Steps       : {run.steps_taken}")
    if run.loot_summary:
        print(f"  Discoveries : {', '.join(run.loot_summary)}")
    print()
    for entry in sim.get_adventure_details(run.adventure_id):
        print(f"  {dim('窶｢')} {entry}")
    _pause()


def _resolve_pending_adventure_choice(sim: Simulator) -> None:
    """Resolve a pending adventure choice through the CLI."""
    pending = sim.get_pending_adventure_choices()
    print()
    if not pending:
        print(dim("  No pending adventure choices."))
        _pause()
        return

    for i, item in enumerate(pending, 1):
        options = ", ".join(item["options"])
        print(
            f"  {i:>2}. {item['character_name']} | {item['prompt']} "
            f"[{options}] default={item['default_option']}"
        )
    print()

    raw = input("  Enter pending choice number (or ENTER to cancel): ").strip()
    if not raw or not raw.isdigit():
        return

    idx = int(raw) - 1
    if not (0 <= idx < len(pending)):
        return

    item = pending[idx]
    options = item["options"]
    print()
    for i, option in enumerate(options, 1):
        default_marker = " (default)" if option == item["default_option"] else ""
        print(f"  {i:>2}. {option}{default_marker}")
    raw_option = input("  Enter option number (or ENTER for default): ").strip()
    chosen_option = None
    if raw_option.isdigit():
        option_idx = int(raw_option) - 1
        if 0 <= option_idx < len(options):
            chosen_option = options[option_idx]

    resolved = sim.resolve_adventure_choice(item["adventure_id"], option=chosen_option)
    print()
    if resolved:
        print(green("  Choice resolved."))
    else:
        print(red("  Could not resolve that choice."))
    _pause()


def _save_simulation_snapshot(sim: Simulator) -> None:
    """Save the current simulation state to a JSON file."""
    print()
    default_name = "simulation_snapshot.json"
    path = input(f"  Save path (default {default_name}): ").strip() or default_name
    try:
        save_simulation(sim, path)
    except OSError as exc:
        print(red(f"  Could not save snapshot: {exc}"))
    else:
        print(green(f"  Snapshot saved to {path}."))
    _pause()


def _load_simulation_snapshot() -> Optional[Simulator]:
    """Load a saved simulation snapshot from disk."""
    print("\n" + _hr("笊・))
    print(bold("  LOAD SIMULATION SNAPSHOT"))
    print(_hr("笊・))
    default_name = "simulation_snapshot.json"
    path = input(f"  Load path (default {default_name}): ").strip() or default_name
    try:
        sim = load_simulation(path)
    except FileNotFoundError:
        print(red(f"  Snapshot not found: {path}"))
        _pause()
        return None
    except (OSError, ValueError, KeyError) as exc:
        print(red(f"  Could not load snapshot: {exc}"))
        _pause()
        return None

    print(green(f"  Loaded snapshot from {path}."))
    return sim


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------

def screen_new_simulation() -> None:
    """Option 1 — run with default world and random characters."""
    print("\n" + _hr("═"))
    print(bold("  NEW SIMULATION — Default World"))
    print(_hr("═"))

    raw = input("  > Number of characters (default 12): ").strip()
    num = int(raw) if raw.isdigit() else 12
    num = max(4, min(30, num))

    raw = input("  > Simulation length in years (default 20): ").strip()
    years = int(raw) if raw.isdigit() else 20
    years = max(1, min(200, years))

    world = _build_default_world(num_characters=num)
    print(f"\n  {green('✓')}  World '{world.name}' created with {num} adventurers.")
    sim = _run_simulation(world, years)
    _show_results(sim)


def screen_custom_simulation() -> None:
    """Option 2 — create custom characters, then simulate."""
    print("\n" + _hr("═"))
    print(bold("  CUSTOM CHARACTER SIMULATION"))
    print(_hr("═"))
    creator = CharacterCreator()
    world = World()
    custom_chars: List[Character] = []

    while True:
        action = _choose(
            "Add a character or start simulation",
            [
                "Create character interactively",
                "Create random character",
                "Create from template",
                f"Start simulation (current roster: {len(custom_chars)} characters)",
            ],
        )

        if action == "Create character interactively":
            char = creator.create_interactive()
            world.add_character(char)
            custom_chars.append(char)
            print(f"\n  {green('✓')}  {char.name} added to the world.")

        elif action == "Create random character":
            char = creator.create_random()
            world.add_character(char)
            custom_chars.append(char)
            print(f"\n  {green('✓')}  {char.name} ({char.race} {char.job}) added randomly.")

        elif action == "Create from template":
            templates = CharacterCreator.list_templates()
            print("\n  Available templates: " + ", ".join(templates))
            tmpl_name = input("  > Template name: ").strip()
            char_name = input("  > Character name (leave blank for random): ").strip() or None
            try:
                char = creator.create_from_template(tmpl_name, name=char_name)
                world.add_character(char)
                custom_chars.append(char)
                print(f"\n  {green('✓')}  {char.name} ({char.race} {char.job}) added from template.")
            except ValueError as exc:
                print(red(f"  Error: {exc}"))

        else:
            # Start simulation
            if not custom_chars:
                print(yellow("  You need at least one character. Adding 5 random ones."))
                for _ in range(5):
                    c = creator.create_random()
                    world.add_character(c)

            # Fill up world with random NPCs to make it more interesting
            fill = max(0, 8 - len(world.characters))
            for _ in range(fill):
                npc = creator.create_random()
                world.add_character(npc)

            raw = input("  > Simulation length in years (default 20): ").strip()
            years = int(raw) if raw.isdigit() else 20
            years = max(1, min(200, years))

            sim = _run_simulation(world, years)
            _show_results(sim)
            break


def screen_world_lore() -> None:
    """Option 3 — display world lore."""
    print("\n" + _hr("═"))
    print(bold("  WORLD LORE — AETHORIA"))
    print(_hr("═"))
    _print_wrapped(WORLD_LORE)
    print()
    from world_data import RACES, JOBS
    print(bold("  RACES OF AETHORIA"))
    print(_hr())
    for rname, rdesc, bonuses in RACES:
        bonus_str = ", ".join(
            f"{stat} {'+' if v >= 0 else ''}{v}"
            for stat, v in bonuses.items() if v != 0
        )
        print(f"  {cyan(rname)}")
        _print_wrapped(rdesc)
        if bonus_str:
            print(f"    {dim('Bonuses:')} {bonus_str}")
        print()
    print(bold("  JOBS / CLASSES"))
    print(_hr())
    from world_data import JOBS
    for jname, jdesc, jskills in JOBS:
        print(f"  {cyan(jname)}  |  Primary skills: {', '.join(jskills)}")
        _print_wrapped(jdesc)
        print()
    _pause()


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def main() -> None:
    print(yellow(HEADER))

    while True:
        print("\n" + _hr("═"))
        print(bold("  MAIN MENU"))
        print(_hr("═"))
        choice = _choose(
            "Choose an option",
            [
                "Start new simulation (default world + random characters)",
                "Create custom characters, then simulate",
                "Load saved simulation snapshot",
                "Read world lore & settings",
                "Exit",
            ],
            default="1",
        )

        if choice.startswith("Start"):
            screen_new_simulation()
        elif choice.startswith("Create"):
            screen_custom_simulation()
        elif choice.startswith("Load"):
            sim = _load_simulation_snapshot()
            if sim is not None:
                _show_results(sim)
        elif choice.startswith("Read"):
            screen_world_lore()
        else:
            print(f"\n  {bold(yellow('Farewell, traveller. May the ley-lines guide your path.'))}\n")
            sys.exit(0)


if __name__ == "__main__":
    main()
