"""Population maintenance helpers for long-running worlds."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from ..character_creator import CharacterCreator
from ..i18n import tr, tr_term
from .calendar import annual_probability_to_fraction

if TYPE_CHECKING:
    from ..character import Character
    from ..world import LocationState, World


BASELINE_POPULATION = 20
MAX_POPULATION_PRESSURE_FACTOR = 4.0
LOCATION_POPULATION_CAPACITY = 6
MAX_MIGRANTS_PER_YEAR = 3
BACKGROUND_MIGRATION_INTERVAL_YEARS = 25


def living_characters(world: "World") -> list["Character"]:
    return [char for char in world.characters if char.alive]


def population_pressure_factor(world: "World") -> float:
    """Scale yearly activity by living population without starving small worlds."""
    return min(MAX_POPULATION_PRESSURE_FACTOR, max(1.0, len(living_characters(world)) / BASELINE_POPULATION))


def population_capacity(world: "World") -> int:
    """Return a soft population capacity for long-run simulation throughput."""
    habitable_locations = [
        location for location in world.grid.values()
        if getattr(location, "region_type", "") != "dungeon"
    ]
    return max(BASELINE_POPULATION, len(habitable_locations) * LOCATION_POPULATION_CAPACITY)


def has_population_capacity(world: "World") -> bool:
    return len(living_characters(world)) < population_capacity(world)


def _location_pull_score(location: "LocationState") -> float:
    """Return a migration pull score from durable location state."""
    return max(
        0.05,
        (location.safety * 0.45 + location.traffic * 0.35 + location.prosperity * 0.20) / 100.0,
    )


def choose_migration_destination(world: "World", rng: Any) -> "LocationState | None":
    candidates = list(world.grid.values())
    if not candidates:
        return None
    weights = [_location_pull_score(location) for location in candidates]
    if hasattr(rng, "choices"):
        return rng.choices(candidates, weights=weights, k=1)[0]
    return rng.choice(candidates)


def minimum_living_population(starting_population: int) -> int:
    if starting_population <= 0:
        return 0
    return max(3, int(starting_population * 0.60))


def yearly_migrant_budget(
    world: "World",
    rng: Any,
    *,
    starting_population: int,
    year_fraction: float = 1.0,
) -> int:
    """Return how many migrant adventurers should enter this year."""
    living_count = len(living_characters(world))
    if living_count >= population_capacity(world):
        return 0
    population_floor = minimum_living_population(starting_population)
    shortfall = max(0, population_floor - living_count)
    if shortfall > 0:
        return min(MAX_MIGRANTS_PER_YEAR, shortfall)
    recent_immigration = any(
        record.kind == "immigration"
        and 0 <= world.year - record.year < BACKGROUND_MIGRATION_INTERVAL_YEARS
        for record in getattr(world, "event_records", [])
    )
    if (
        starting_population >= BASELINE_POPULATION
        and living_count <= starting_population + 3
        and world.year % BACKGROUND_MIGRATION_INTERVAL_YEARS == 0
        and not recent_immigration
    ):
        return 1
    if starting_population < BASELINE_POPULATION and living_count >= starting_population:
        return 0
    annual_chance = min(0.45, max(0.0, (BASELINE_POPULATION - living_count) * 0.05))
    chance = annual_probability_to_fraction(annual_chance, year_fraction)
    return 1 if rng.random() < chance else 0


def add_migrant_adventurers(
    world: "World",
    rng: Any,
    *,
    starting_population: int,
    year_fraction: float = 1.0,
) -> list["Character"]:
    """Create migrant adventurers as a population stabilizer."""
    budget = yearly_migrant_budget(world, rng, starting_population=starting_population, year_fraction=year_fraction)
    if budget <= 0:
        return []

    creator = CharacterCreator(setting_bundle=world.setting_bundle)
    migrants: list["Character"] = []
    for _ in range(budget):
        destination = choose_migration_destination(world, rng)
        if destination is None:
            break
        try:
            migrant = creator.create_random(rng=rng)
        except (AttributeError, ValueError):
            break
        migrant.location_id = destination.id
        migrant.add_history(
            tr("history_migrated_to_world", year=world.year, location=world.location_name(destination.id))
        )
        world.add_character(migrant, rng=rng)
        migrants.append(migrant)
    return migrants


def migration_summary(migrants: list["Character"], world: "World") -> str:
    if len(migrants) == 1:
        migrant = migrants[0]
        return tr(
            "population_migrant_arrived",
            name=migrant.name,
            race=tr_term(migrant.race),
            job=tr_term(migrant.job),
            location=world.location_name(migrant.location_id),
        )
    return tr("population_migrants_arrived", count=len(migrants))


def run_population_maintenance(simulator: Any) -> None:
    """Run migration maintenance for a simulator-like object."""
    if not getattr(simulator, "population_maintenance_enabled", True):
        return
    if (
        simulator.events_per_year <= 0
        and simulator.adventure_steps_per_year <= 0
        and simulator.world_changes_per_year <= 0
    ):
        return
    migrants = add_migrant_adventurers(
        simulator.world,
        simulator.rng,
        starting_population=simulator.starting_population,
    )
    if not migrants:
        return
    primary = migrants[0]
    simulator._record_world_event(
        migration_summary(migrants, simulator.world),
        kind="immigration",
        location_id=primary.location_id,
        primary_actor_id=primary.char_id,
        secondary_actor_ids=[char.char_id for char in migrants[1:]],
        severity=2,
    )
