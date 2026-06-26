"""Deterministic seeded simulation statistics for local benchmark checks."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from typing import Any, Sequence

from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.simulation import Simulator
from fantasy_simulator.world import World


@dataclass(frozen=True)
class PopulationSnapshot:
    """Population state at a deterministic simulation checkpoint."""

    year: int
    month: int
    elapsed_months: int
    total: int
    alive: int
    deceased: int
    births: int
    deaths: int
    immigrations: int
    by_location: dict[str, int]


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
    event_records_json_bytes: int
    rumor_archive_json_bytes: int
    save_json_bytes: int
    alive: int
    population_series: list[PopulationSnapshot]


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


def collect_population_snapshot(simulator: Simulator, *, elapsed_months: int) -> PopulationSnapshot:
    """Return a location-mapped population snapshot for the simulator's current state."""
    world = simulator.world
    by_location: dict[str, int] = {}
    alive = 0
    deceased = 0
    for character in world.characters:
        if character.alive:
            alive += 1
            by_location[world.location_name(character.location_id)] = (
                by_location.get(world.location_name(character.location_id), 0) + 1
            )
        else:
            deceased += 1
    return PopulationSnapshot(
        year=world.year,
        month=simulator.current_month,
        elapsed_months=elapsed_months,
        total=len(world.characters),
        alive=alive,
        deceased=deceased,
        births=sum(1 for record in world.event_records if record.kind == "birth"),
        deaths=sum(1 for record in world.event_records if record.kind in {"death", "adventure_death"}),
        immigrations=sum(1 for record in world.event_records if record.kind == "immigration"),
        by_location=dict(sorted(by_location.items())),
    )


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
    population_series = [collect_population_snapshot(simulator, elapsed_months=0)]
    elapsed_months = 0
    for _ in range(years):
        simulator.advance_months(world.months_per_year)
        elapsed_months += world.months_per_year
        population_series.append(collect_population_snapshot(simulator, elapsed_months=elapsed_months))
    if months:
        simulator.advance_months(months)
        elapsed_months += months
        population_series.append(collect_population_snapshot(simulator, elapsed_months=elapsed_months))
    event_payloads = [record.to_dict() for record in world.event_records]
    rumor_archive_payloads = [rumor.to_dict() for rumor in world.rumor_archive]

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
        event_records_json_bytes=_json_size_bytes(event_payloads),
        rumor_archive_json_bytes=_json_size_bytes(rumor_archive_payloads),
        save_json_bytes=_json_size_bytes(simulator.to_dict()),
        alive=sum(1 for character in world.characters if character.alive),
        population_series=population_series,
    )


def _json_size_bytes(payload: Any) -> int:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return len(text.encode("utf-8"))


def format_stats(stats: SimulationStats) -> str:
    """Format stats as stable, line-oriented text."""
    data = asdict(stats)
    population_series = data.pop("population_series")
    lines = [f"{key}: {data[key]}" for key in data]
    lines.append("population_series:")
    for snapshot in population_series:
        locations = ", ".join(
            f"{name}={count}" for name, count in snapshot["by_location"].items()
        )
        lines.append(
            "  "
            f"month {snapshot['elapsed_months']}: "
            f"year={snapshot['year']} current_month={snapshot['month']} "
            f"alive={snapshot['alive']} deceased={snapshot['deceased']} "
            f"births={snapshot['births']} deaths={snapshot['deaths']} "
            f"immigrations={snapshot['immigrations']} locations=[{locations}]"
        )
    return "\n".join(lines)


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
