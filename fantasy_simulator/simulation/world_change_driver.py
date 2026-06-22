"""Natural PR-K world-change generation during simulation."""

from __future__ import annotations

from typing import Any

from ..combat import resolve_combat
from ..event_models import LOCATION_TAG_PREFIX, WorldEventRecord, generate_record_id
from ..event_rendering import render_event_record
from ..observation import build_war_map_projection
from ..rumor import generate_tracked_rumor_from_world_change
from ..terrain import BIOME_TYPES
from .. import world_language_facade
from ..world_arcs import active_world_arcs, attach_record_to_arc, last_arc_event_id
from ..world_location_state import clamp_state

NATURAL_ERA_KEYS = (
    "age_of_reckoning",
    "age_of_bloom",
    "age_of_tides",
    "age_of_stars",
    "age_of_silence",
    "age_of_embers",
)

MIN_NATURAL_ERA_SHIFT_INTERVAL_YEARS = 25


class WarBandCombatant:
    """Ephemeral combatant used to resolve faction-scale war arc battles."""

    def __init__(
        self,
        *,
        faction_id: str,
        location_id: str,
        combat_power: int,
        constitution: int,
        skills: dict[str, int],
    ) -> None:
        self.char_id = f"warband:{faction_id}"
        self.name = faction_id
        self.location_id = location_id
        self.injury_status = "none"
        self._combat_power = combat_power
        self.constitution = constitution
        self.dexterity = max(20, combat_power // 2)
        self.intelligence = max(20, combat_power // 3)
        self.wisdom = max(20, combat_power // 3)
        self.skills = dict(skills)

    @property
    def combat_power(self) -> int:
        return self._combat_power

    def apply_stat_delta(self, deltas: dict[str, int]) -> None:
        del deltas

    def update_mutual_relationship(self, other: Any, delta: int, delta_other: int | None = None) -> None:
        del other, delta, delta_other

    def worsen_injury(self) -> str:
        return self.injury_status

    def add_history(self, event: str) -> None:
        del event

    def add_relation_tag(self, other_id: str, tag: str, source_event_id: str | None = None) -> None:
        del other_id, tag, source_event_id


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


def _faction_tag(faction_id: str) -> str:
    return f"faction:{faction_id}"


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


def _site_language_for_location(world: Any, location_id: str) -> tuple[str, str]:
    for seed in world.setting_bundle.world_definition.site_seeds:
        if seed.location_id == location_id:
            return seed.language_key, seed.region_type
    language = world.language_engine.resolve_language(region=location_id)
    return (language.language_key if language is not None else "", "")


def _language_rename_candidate_payloads(world: Any, location: Any) -> list[dict[str, str]]:
    location_id = str(getattr(location, "id", "")).strip()
    if not location_id:
        return []
    language_key, region_type = _site_language_for_location(world, location_id)
    if not language_key:
        return []
    current_name = str(location.canonical_name).strip()
    faction_id = str(getattr(location, "controlling_faction_id", "") or "").strip()
    return [
        {
            "new_name": world.language_engine.generate_toponym(
                language_key,
                seed_key=f"rename:{location_id}:{current_name}:{faction_id}:{index}",
                region_type=region_type,
            ),
            "name_language_key": language_key,
            "name_language_seed_key": f"rename:{location_id}:{current_name}:{faction_id}:{index}",
            "name_language_region_type": region_type,
            "name_source": "language_generated_rename",
        }
        for index in range(4)
    ]


def _natural_rename_payload(world: Any, location: Any) -> dict[str, str] | None:
    current_name = str(location.canonical_name).strip()
    fallback_candidates = [
        {"new_name": candidate, "name_source": "fallback_rename_template"}
        for candidate in _rename_candidates(location)
    ]
    for candidate in _language_rename_candidate_payloads(world, location) + fallback_candidates:
        normalized = candidate["new_name"].strip()
        if normalized and normalized != current_name and not _location_name_exists(world, normalized):
            return {**candidate, "new_name": normalized}
    return None


def _faction_pairs(faction_ids: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for idx, first in enumerate(faction_ids):
        for second in faction_ids[idx + 1:]:
            pairs.append((first, second))
    return pairs


def generate_war_world_change(world: Any, *, month: int, day: int, rng: Any) -> Any | None:
    """Generate one natural war declaration or war ending from canonical war history."""
    active_arcs = active_world_arcs(world, kind="war")
    if active_arcs and rng.random() < 0.70:
        return generate_war_arc_pulse(world, month=month, day=day, rng=rng)

    projection = build_war_map_projection(
        event_records=getattr(world, "event_records", []),
        faction_relationships=_authored_faction_relationships(world),
    )
    if active_arcs and rng.random() < 0.55:
        arc = rng.choice(active_arcs)
        aggressor, target = arc.participant_faction_ids[:2]
        return _record_and_track_world_change(
            world,
            world.apply_war_ended(
                aggressor,
                target,
                location_ids=arc.location_ids,
                month=month,
                day=day,
                cause_key="natural_war_resolution",
                cause_event_id=last_arc_event_id(arc),
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


def generate_war_arc_pulse(world: Any, *, month: int, day: int, rng: Any) -> Any | None:
    """Advance one active persistent war arc with a concrete world-change event."""
    active_arcs = active_world_arcs(world, kind="war")
    if not active_arcs:
        return None
    arc = rng.choice(active_arcs)
    roll = rng.random()
    if roll < 0.20:
        return _end_war_arc(world, arc, month=month, day=day)
    if roll < 0.60:
        return _occupy_war_arc_location(world, arc, month=month, day=day, rng=rng)
    return _record_war_battle(world, arc, month=month, day=day, rng=rng)


def _valid_arc_location_ids(world: Any, arc: Any) -> list[str]:
    location_ids = [
        location_id for location_id in arc.location_ids
        if isinstance(location_id, str) and world.get_location_by_id(location_id) is not None
    ]
    if location_ids:
        return sorted(location_ids)
    return sorted(getattr(world, "location_ids", []))


def _end_war_arc(world: Any, arc: Any, *, month: int, day: int) -> Any | None:
    aggressor, target = arc.participant_faction_ids[:2]
    return _record_and_track_world_change(
        world,
        world.apply_war_ended(
            aggressor,
            target,
            location_ids=arc.location_ids,
            month=month,
            day=day,
            cause_key="war_arc_resolution",
            cause_event_id=last_arc_event_id(arc),
        ),
    )


def _occupy_war_arc_location(world: Any, arc: Any, *, month: int, day: int, rng: Any) -> Any | None:
    location_ids = _valid_arc_location_ids(world, arc)
    if not location_ids:
        return None
    location_id = rng.choice(location_ids)
    location = world.get_location_by_id(location_id)
    if location is None:
        return None
    faction_ids = list(arc.participant_faction_ids[:2])
    if not faction_ids:
        return None
    faction_id = rng.choice(faction_ids)
    if location.controlling_faction_id == faction_id and len(faction_ids) > 1:
        faction_id = faction_ids[1] if faction_id == faction_ids[0] else faction_ids[0]
    record = world.apply_controlling_faction_change(
        location_id,
        faction_id,
        month=month,
        day=day,
        allow_unknown_faction=True,
        cause_event_id=last_arc_event_id(arc),
    )
    if record is not None:
        attach_record_to_arc(arc, record)
    return _record_and_track_world_change(world, record)


def _record_war_battle(world: Any, arc: Any, *, month: int, day: int, rng: Any) -> Any | None:
    location_ids = _valid_arc_location_ids(world, arc)
    faction_ids = list(arc.participant_faction_ids[:2])
    if not location_ids or len(faction_ids) < 2:
        return None
    location_id = rng.choice(location_ids)
    attacker, defender = faction_ids
    if rng.random() < 0.5:
        attacker, defender = defender, attacker
    combat_resolution = resolve_combat(
        _war_band(attacker, location_id, world),
        _war_band(defender, location_id, world),
        rng,
    )
    record = WorldEventRecord(
        record_id=generate_record_id(rng),
        kind="war_battle",
        year=world.year,
        month=month,
        day=day,
        location_id=location_id,
        description="",
        severity=4,
        summary_key="events.war_battle.summary",
        render_params={
            "arc_id": arc.arc_id,
            "attacker_faction_id": attacker,
            "defender_faction_id": defender,
            "participant_faction_ids": faction_ids,
            "location_id": location_id,
            "cause_event_id": last_arc_event_id(arc),
            "winner_faction_id": _war_band_faction_id(combat_resolution.winner.char_id),
            "loser_faction_id": _war_band_faction_id(combat_resolution.loser.char_id),
            "combat_log": combat_resolution.combat_log_payload(),
        },
        tags=[
            "world_change",
            "war",
            "battle",
            f"arc:{arc.arc_id}",
            f"{LOCATION_TAG_PREFIX}{location_id}",
            _faction_tag(attacker),
            _faction_tag(defender),
        ],
    )
    record.description = render_event_record(record, world=world)
    stored_record = world.record_event(record)
    _apply_war_battle_pressure(world, stored_record)
    world_language_facade.apply_language_evolution_from_event(
        world,
        stored_record,
        cause_key="war_battle",
    )
    attach_record_to_arc(arc, stored_record)
    return _record_and_track_world_change(world, stored_record)


def _war_band(faction_id: str, location_id: str, world: Any) -> WarBandCombatant:
    location = world.get_location_by_id(location_id)
    danger = int(getattr(location, "danger", 40)) if location is not None else 40
    safety = int(getattr(location, "safety", 50)) if location is not None else 50
    controlled_by_faction = getattr(location, "controlling_faction_id", None) == faction_id if location else False
    home_bonus = 8 if controlled_by_faction else 0
    return WarBandCombatant(
        faction_id=faction_id,
        location_id=location_id,
        combat_power=45 + danger // 4 + home_bonus,
        constitution=55 + safety // 5 + home_bonus,
        skills={
            "Swordsmanship": 2 + home_bonus // 4,
            "Shield Block": 1 + safety // 50,
            "Battle Cry": 1 + danger // 80,
        },
    )


def _war_band_faction_id(char_id: str) -> str:
    prefix = "warband:"
    return char_id[len(prefix):] if char_id.startswith(prefix) else char_id


def _apply_war_battle_pressure(world: Any, record: WorldEventRecord) -> None:
    location = world.get_location_by_id(record.location_id) if record.location_id else None
    if location is None:
        return
    for attr, delta in {
        "danger": 10,
        "rumor_heat": 14,
        "safety": -7,
        "mood": -5,
        "road_condition": -4,
    }.items():
        setattr(location, attr, clamp_state(int(getattr(location, attr)) + delta))


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
        rename_payload = _natural_rename_payload(world, location)
        if rename_payload is None:
            candidates = [candidate for candidate in candidates if candidate is not location]
            continue
        record = world.apply_location_rename_change(
            location.id,
            rename_payload["new_name"],
            month=month,
            day=day,
        )
        if record is not None:
            record.render_params.update({
                key: value
                for key, value in rename_payload.items()
                if key != "new_name" and value
            })
        return _record_and_track_world_change(world, record)
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
    last_era_shift_year = max(
        (record.year for record in getattr(world, "event_records", []) if record.kind == "era_shifted"),
        default=None,
    )
    if (
        last_era_shift_year is not None
        and world.year - last_era_shift_year < MIN_NATURAL_ERA_SHIFT_INTERVAL_YEARS
    ):
        return None
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
