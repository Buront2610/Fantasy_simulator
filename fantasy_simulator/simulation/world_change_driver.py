"""Natural PR-K world-change generation during simulation."""

from __future__ import annotations

from typing import Any

from ..observation import build_war_map_projection
from ..rumor import generate_tracked_rumor_from_world_change
from ..terrain import BIOME_TYPES

NATURAL_ERA_KEYS = (
    "age_of_reckoning",
    "age_of_bloom",
    "age_of_tides",
    "age_of_stars",
    "age_of_silence",
    "age_of_embers",
)


def _setting_entry_key(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_").replace("'", "")


def _bounded_delta(value: int, *, delta: int) -> int:
    return max(0, min(255, int(value) + delta))


def _next_biome(current_biome: str, rng: Any) -> str:
    candidates = [biome for biome in BIOME_TYPES if biome != current_biome]
    if not candidates:
        return current_biome
    return rng.choice(sorted(candidates))


def _authored_faction_ids(world: Any) -> list[str]:
    bundle = getattr(world, "_setting_bundle", None)
    if bundle is None:
        bundle = getattr(world, "setting_bundle", None)
    world_definition = getattr(bundle, "world_definition", None)
    faction_entries = getattr(world_definition, "faction_entries", None)
    if not callable(faction_entries):
        return []

    faction_ids: list[str] = []
    for entry in faction_entries():
        key = getattr(entry, "key", "")
        display_name = getattr(entry, "display_name", "")
        faction_id = key if isinstance(key, str) and key else _setting_entry_key(str(display_name))
        if faction_id and faction_id not in faction_ids:
            faction_ids.append(faction_id)
    return sorted(faction_ids)


def _authored_faction_relationships(world: Any) -> list[Any]:
    bundle = getattr(world, "_setting_bundle", None)
    if bundle is None:
        bundle = getattr(world, "setting_bundle", None)
    world_definition = getattr(bundle, "world_definition", None)
    return list(getattr(world_definition, "faction_relationships", ()))


def _affected_location_ids(world: Any, rng: Any) -> tuple[str, ...]:
    location_ids = sorted(getattr(world, "location_ids", []))
    if len(location_ids) <= 2:
        return tuple(location_ids)
    first = rng.choice(location_ids)
    remaining = [location_id for location_id in location_ids if location_id != first]
    second = rng.choice(remaining)
    return tuple(sorted((first, second)))


def _record_and_track_world_change(world: Any, record: Any | None) -> Any | None:
    if record is None:
        return None
    existing_source_event_ids = {getattr(rumor, "source_event_id", None) for rumor in getattr(world, "rumors", [])}
    existing_source_event_ids.update(
        getattr(rumor, "source_event_id", None)
        for rumor in getattr(world, "rumor_archive", [])
    )
    if getattr(record, "record_id", None) in existing_source_event_ids:
        return record
    rumor = generate_tracked_rumor_from_world_change(record, world=world)
    if rumor is not None:
        world.rumors.append(rumor)
    return record


def _location_name_exists(world: Any, name: str) -> bool:
    try:
        return world.get_location_by_name(name) is not None
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def _faction_name_prefix(faction_id: str) -> str:
    words = faction_id.replace("_", " ").replace("-", " ").title().split()
    return words[0] if words else "Frontier"


def _rename_candidates(location: Any) -> list[str]:
    current_name = str(location.canonical_name).strip()
    base_word = current_name.split()[-1] if current_name.split() else "Hold"
    faction_id = getattr(location, "controlling_faction_id", None)
    if isinstance(faction_id, str) and faction_id.strip():
        prefix = _faction_name_prefix(faction_id)
        return [
            f"{prefix} {base_word}",
            f"{prefix} March",
            f"{prefix} Ward",
            f"{prefix} Hold",
        ]
    return [
        f"{current_name} March",
        f"{current_name} Ward",
        f"{current_name} Haven",
        f"{current_name} Hold",
    ]


def _natural_rename_name(world: Any, location: Any) -> str | None:
    current_name = str(location.canonical_name).strip()
    for candidate in _rename_candidates(location):
        normalized = candidate.strip()
        if normalized and normalized != current_name and not _location_name_exists(world, normalized):
            return normalized
    return None


def _faction_pairs(faction_ids: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for idx, first in enumerate(faction_ids):
        for second in faction_ids[idx + 1:]:
            pairs.append((first, second))
    return pairs


def generate_war_world_change(world: Any, *, month: int, day: int, rng: Any) -> Any | None:
    """Generate one natural war declaration or war ending from canonical war history."""
    projection = build_war_map_projection(
        event_records=getattr(world, "event_records", []),
        faction_relationships=_authored_faction_relationships(world),
    )
    if projection.active_wars and rng.random() < 0.55:
        war = rng.choice(list(projection.active_wars))
        return _record_and_track_world_change(
            world,
            world.apply_war_ended(
                war.aggressor_faction_id,
                war.target_faction_id,
                location_ids=war.location_ids,
                month=month,
                day=day,
                cause_key="natural_war_resolution",
            ),
        )

    faction_ids = _authored_faction_ids(world)
    if len(faction_ids) < 2:
        return None
    active_pairs = {war.faction_ids for war in projection.active_wars}
    available_pairs = [pair for pair in _faction_pairs(faction_ids) if pair not in active_pairs]
    if not available_pairs:
        if not projection.active_wars:
            return None
        war = rng.choice(list(projection.active_wars))
        return _record_and_track_world_change(
            world,
            world.apply_war_ended(
                war.aggressor_faction_id,
                war.target_faction_id,
                location_ids=war.location_ids,
                month=month,
                day=day,
                cause_key="natural_war_resolution",
            ),
        )
    aggressor, target = rng.choice(available_pairs)
    return _record_and_track_world_change(
        world,
        world.apply_war_declaration(
            aggressor,
            target,
            location_ids=_affected_location_ids(world, rng),
            month=month,
            day=day,
            cause_key="natural_faction_conflict",
        ),
    )


def generate_occupation_world_change(world: Any, *, month: int, day: int, rng: Any) -> Any | None:
    """Generate one natural location-control shift from active faction-war history."""
    projection = build_war_map_projection(
        event_records=getattr(world, "event_records", []),
        faction_relationships=_authored_faction_relationships(world),
    )
    if not projection.active_wars:
        return None

    war = rng.choice(list(projection.active_wars))
    location_ids = [location_id for location_id in war.location_ids if world.get_location_by_id(location_id)]
    if not location_ids:
        return None

    location_id = rng.choice(sorted(location_ids))
    location = world.get_location_by_id(location_id)
    if location is None:
        return None

    candidates = [war.aggressor_faction_id, war.target_faction_id]
    faction_id = rng.choice(candidates)
    if location.controlling_faction_id == faction_id:
        faction_id = candidates[1] if faction_id == candidates[0] else candidates[0]
    return _record_and_track_world_change(
        world,
        world.apply_controlling_faction_change(
            location_id,
            faction_id,
            month=month,
            day=day,
        ),
    )


def generate_rename_world_change(world: Any, *, month: int, day: int, rng: Any) -> Any | None:
    """Generate one natural official location rename, if a non-conflicting name is available."""
    locations = [
        location
        for location_id in sorted(getattr(world, "location_ids", []))
        for location in [world.get_location_by_id(location_id)]
        if location is not None
    ]
    if not locations:
        return None

    controlled = [
        location
        for location in locations
        if isinstance(getattr(location, "controlling_faction_id", None), str)
        and str(getattr(location, "controlling_faction_id")).strip()
    ]
    candidates = controlled or locations
    while candidates:
        location = rng.choice(candidates)
        new_name = _natural_rename_name(world, location)
        if new_name is None:
            candidates = [candidate for candidate in candidates if candidate is not location]
            continue
        return _record_and_track_world_change(
            world,
            world.apply_location_rename_change(
                location.id,
                new_name,
                month=month,
                day=day,
            ),
        )
    return None


def generate_terrain_world_change(world: Any, *, month: int, day: int, rng: Any) -> Any | None:
    """Generate one location-linked terrain mutation, if terrain is available."""
    terrain_map = getattr(world, "terrain_map", None)
    if terrain_map is None:
        return None

    locations = []
    for location_id in sorted(world.location_ids):
        location = world.get_location_by_id(location_id)
        if location is not None and terrain_map.get(location.x, location.y) is not None:
            locations.append(location)
    if not locations:
        return None

    location = rng.choice(locations)
    cell = terrain_map.get(location.x, location.y)
    if cell is None:
        return None
    return _record_and_track_world_change(
        world,
        world.apply_terrain_cell_change(
            cell.x,
            cell.y,
            biome=_next_biome(cell.biome, rng),
            moisture=_bounded_delta(cell.moisture, delta=rng.choice((-18, -12, 12, 18))),
            temperature=_bounded_delta(cell.temperature, delta=rng.choice((-10, -6, 6, 10))),
            location_id=location.id,
            month=month,
            day=day,
            reason_key="natural_environment_shift",
        ),
    )


def generate_civilization_world_change(world: Any, *, month: int, day: int, rng: Any) -> Any | None:
    """Generate one civilization-phase drift, if it would change the current phase."""
    runtime = world._world_era_runtime()
    era_rules = world._era_runtime_rules()
    phases = [phase for phase in era_rules.civilization_phases if phase != runtime.civilization_phase]
    if not phases:
        return None
    phase = rng.choice(sorted(phases))
    delta_options = {
        "prosperity": (-4, -2, 2, 4),
        "safety": (-6, -3, 3, 6),
        "traffic": (-4, -2, 2, 4),
        "mood": (-5, -2, 2, 5),
    }
    score_deltas = {
        score_key: rng.choice(delta_options.get(score_key, (-3, -1, 1, 3)))
        for score_key in era_rules.world_score_keys
    }
    return _record_and_track_world_change(
        world,
        world.apply_civilization_phase_drift(
            phase,
            score_deltas=score_deltas,
            month=month,
            day=day,
            reason_key="natural_civilization_drift",
        ),
    )


def generate_era_world_change(world: Any, *, month: int, day: int, rng: Any) -> Any | None:
    """Generate one natural era shift, if a different era key is available."""
    runtime = world._world_era_runtime()
    candidates = [era_key for era_key in NATURAL_ERA_KEYS if era_key != runtime.era_key]
    if not candidates:
        return None
    new_era_key = rng.choice(sorted(candidates))
    era_rules = world._era_runtime_rules()
    new_phase = "new_era" if "new_era" in era_rules.civilization_phases else era_rules.civilization_phases[0]
    return _record_and_track_world_change(
        world,
        world.apply_era_shift(
            new_era_key,
            new_civilization_phase=new_phase,
            authored_era_keys={runtime.era_key, new_era_key},
            month=month,
            day=day,
            cause_key="natural_era_turning",
        ),
    )


def generate_route_world_change(world: Any, *, month: int, day: int, rng: Any) -> Any | None:
    """Generate one route disruption/reopening world change, if routes are available."""
    routes = sorted(world.routes, key=lambda route: route.route_id)
    if not routes:
        return None

    blocked_routes = [route for route in routes if route.blocked]
    open_routes = [route for route in routes if not route.blocked]
    if blocked_routes and (not open_routes or rng.random() < 0.35):
        route = rng.choice(blocked_routes)
        return _record_and_track_world_change(
            world,
            world.apply_route_blocked_change(route.route_id, False, month=month, day=day),
        )
    if not open_routes:
        return None
    route = rng.choice(open_routes)
    return _record_and_track_world_change(
        world,
        world.apply_route_blocked_change(route.route_id, True, month=month, day=day),
    )


def generate_world_change(world: Any, *, month: int, day: int, rng: Any) -> Any | None:
    """Generate one natural world change across the currently wired PR-K slices."""
    generators = [
        generate_route_world_change,
        generate_terrain_world_change,
        generate_civilization_world_change,
        generate_era_world_change,
        generate_war_world_change,
        generate_occupation_world_change,
        generate_rename_world_change,
    ]
    while generators:
        generator = rng.choice(generators)
        generators.remove(generator)
        record = generator(world, month=month, day=day, rng=rng)
        if record is not None:
            return record
    return None
