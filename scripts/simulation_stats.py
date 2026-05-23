"""Deterministic seeded simulation statistics for local benchmark checks."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from typing import Any, Sequence

from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World


@dataclass(frozen=True)
class SimulationStats:
    """Small, serializable summary of a seeded simulation run."""

    world_seed: int
    simulation_seed: int
    characters: int
    events_per_year: int
    adventure_steps_per_year: int
    years: int
    months: int
    total_months: int
    final_year: int
    final_month: int
    events: int
    rumors: int
    alive: int


def build_seeded_world(seed: int, n_chars: int = 6) -> World:
    """Build a seeded world with a stable non-dungeon roster spread."""
    rng = random.Random(seed)
    world = World()
    creator = CharacterCreator()
    location_ids = [loc.id for loc in world.grid.values() if loc.region_type != "dungeon"]
    for _ in range(n_chars):
        character = creator.create_random(rng=rng)
        character.location_id = rng.choice(location_ids)
        world.add_character(character)
    return world


def collect_simulation_stats(
    *,
    world_seed: int = 7,
    simulation_seed: int = 99,
    years: int = 10,
    months: int = 0,
    characters: int = 6,
    events_per_year: int = 4,
    adventure_steps_per_year: int = 2,
) -> SimulationStats:
    """Run a seeded simulation and return deterministic aggregate counters."""
    if years < 0:
        raise ValueError("years must be non-negative")
    if months < 0:
        raise ValueError("months must be non-negative")
    if characters < 0:
        raise ValueError("characters must be non-negative")

    world = build_seeded_world(world_seed, n_chars=characters)
    simulator = Simulator(
        world,
        events_per_year=events_per_year,
        adventure_steps_per_year=adventure_steps_per_year,
        seed=simulation_seed,
    )
    total_months = years * world.months_per_year + months
    simulator.advance_months(total_months)

    return SimulationStats(
        world_seed=world_seed,
        simulation_seed=simulation_seed,
        characters=characters,
        events_per_year=events_per_year,
        adventure_steps_per_year=adventure_steps_per_year,
        years=years,
        months=months,
        total_months=total_months,
        final_year=world.year,
        final_month=simulator.current_month,
        events=len(world.event_records),
        rumors=len(world.rumors),
        alive=sum(1 for character in world.characters if character.alive),
    )


def format_stats(stats: SimulationStats) -> str:
    """Format stats as stable, line-oriented text."""
    data = asdict(stats)
    return "\n".join(f"{key}: {data[key]}" for key in data)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world-seed", type=int, default=7)
    parser.add_argument("--simulation-seed", type=int, default=99)
    parser.add_argument("--years", type=int, default=10)
    parser.add_argument("--months", type=int, default=0)
    parser.add_argument("--characters", type=int, default=6)
    parser.add_argument("--events-per-year", type=int, default=4)
    parser.add_argument("--adventure-steps-per-year", type=int, default=2)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    stats = collect_simulation_stats(
        world_seed=args.world_seed,
        simulation_seed=args.simulation_seed,
        years=args.years,
        months=args.months,
        characters=args.characters,
        events_per_year=args.events_per_year,
        adventure_steps_per_year=args.adventure_steps_per_year,
    )
    payload: dict[str, Any] = asdict(stats)
    if args.format == "json":
        print(json.dumps(payload, sort_keys=True))
    else:
        print(format_stats(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
