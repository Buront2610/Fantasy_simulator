"""Lifecycle and death-resolution event helpers for EventSystem."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .death_resolution import mark_character_dead
from .event_models import EventResult, generate_record_id
from .i18n import tr
from .simulation.calendar import annual_probability_to_fraction

if TYPE_CHECKING:
    from .character import Character
    from .world import World


DeathEventCallback = Callable[["Character", "World", Any], EventResult]


def character_lifespan_years(char: "Character", world: "World") -> int:
    """Return bundle-authored race lifespan with Character.max_age as compatibility fallback."""
    world_lifespan = world.race_lifespan_years(char.race)
    if world_lifespan is not None:
        return world_lifespan
    return char.max_age


def resolve_aging_event(char: "Character", world: "World", rng: Any = random) -> EventResult:
    """Resolve one annual aging tick for a character."""
    char.age += 1
    max_age = character_lifespan_years(char, world)
    if char.age < 30:
        stat_changes = {
            "strength": rng.randint(0, 2),
            "intelligence": rng.randint(0, 2),
            "dexterity": rng.randint(0, 1),
            "wisdom": rng.randint(0, 1),
        }
        desc = tr("aging_young", name=char.name, age=char.age)
    elif char.age < 50:
        stat_changes = {
            "intelligence": rng.randint(0, 2),
            "wisdom": rng.randint(0, 2),
            "strength": rng.randint(-1, 1),
        }
        desc = tr("aging_prime", name=char.name, age=char.age)
    elif char.age < max_age * 0.75:
        stat_changes = {
            "wisdom": rng.randint(1, 3),
            "charisma": rng.randint(0, 1),
            "dexterity": -rng.randint(0, 2),
            "strength": -rng.randint(0, 1),
        }
        desc = tr("aging_middle", name=char.name, age=char.age)
    else:
        stat_changes = {
            "wisdom": rng.randint(0, 2),
            "strength": -rng.randint(1, 3),
            "dexterity": -rng.randint(1, 3),
            "constitution": -rng.randint(1, 4),
        }
        desc = tr("aging_old", name=char.name, age=char.age)

    char.apply_stat_delta(stat_changes)
    char.add_history(tr("history_turned_age", year=world.year, age=char.age))
    return EventResult(
        description=desc,
        affected_characters=[char.char_id],
        stat_changes={char.char_id: stat_changes},
        event_type="aging",
        year=world.year,
    )


def resolve_death_event(char: "Character", world: "World", rng: Any = random) -> EventResult:
    """Resolve the canonical death event narrative and side effects."""
    mark_character_dead(char, world)

    cause_options = [
        tr("death_cause_old_age"),
        tr("death_cause_monster", location=world.location_name(char.location_id)),
        tr("death_cause_illness"),
        tr("death_cause_protecting"),
        tr("death_cause_dungeon"),
        tr("death_cause_road"),
    ]
    max_age = character_lifespan_years(char, world)
    cause = cause_options[0] if char.age >= max_age * 0.9 else rng.choice(cause_options[1:])
    desc = tr("death_narrative", name=char.name, race=char.race, job=char.job, age=char.age, cause=cause)
    char.add_history(tr("history_passed_away", year=world.year, cause=cause))
    return EventResult(
        description=desc,
        affected_characters=[char.char_id],
        event_type="death",
        year=world.year,
    )


def check_natural_death(
    char: "Character",
    world: "World",
    *,
    event_death: DeathEventCallback,
    rng: Any = random,
    year_fraction: float = 1.0,
) -> Optional[EventResult]:
    """Resolve natural decline, possibly worsening injury or causing death."""
    if not char.alive:
        return None
    age_ratio = char.age / max(character_lifespan_years(char, world), 1)
    con_factor = (100 - char.constitution) / 100 * 0.5 + 0.5
    annual_death_chance = max(0.0, (age_ratio - 0.6) / 0.4) ** 2 * con_factor
    death_chance = annual_probability_to_fraction(annual_death_chance, year_fraction)

    if rng.random() < death_chance:
        if char.injury_status == "dying":
            return event_death(char, world, rng)
        old_status = char.injury_status
        char.worsen_injury()
        if char.injury_status != old_status:
            desc = tr(
                "condition_worsened",
                name=char.name,
                status=tr(f"injury_status_{char.injury_status}"),
            )
            char.add_history(
                tr("history_condition_worsened", year=world.year,
                   status=tr(f"injury_status_{char.injury_status}"))
            )
            return EventResult(
                description=desc,
                affected_characters=[char.char_id],
                event_type="condition_worsened",
                year=world.year,
            )
    return None


def check_dying_resolution(
    char: "Character",
    world: "World",
    *,
    event_death: DeathEventCallback,
    rng: Any = random,
    year_fraction: float = 1.0,
) -> Optional[EventResult]:
    """Resolve dying characters by rescue, stabilization, or death."""
    if not char.alive or char.injury_status != "dying":
        return None
    loc = world.get_location_by_id(char.location_id)
    safety_bonus = (loc.safety / 100.0 * 0.2) if loc else 0.0
    con_bonus = char.constitution / 100.0 * 0.3
    allies_at_loc = [
        c for c in world.get_characters_at_location(char.location_id)
        if c.char_id != char.char_id and c.alive and c.injury_status != "dying"
    ]
    ally_bonus = min(len(allies_at_loc) * 0.1, 0.3)
    annual_rescue_chance = max(0.0, min(0.95, 0.1 + safety_bonus + con_bonus + ally_bonus))
    if year_fraction >= 1.0:
        rescue_roll = rng.random()
        rescue_chance = annual_rescue_chance
        death_chance = 1.0 - rescue_chance
    else:
        rescue_chance = annual_probability_to_fraction(annual_rescue_chance, year_fraction)
        death_chance = annual_probability_to_fraction(1.0 - annual_rescue_chance, year_fraction)
        death_chance = min(death_chance, max(0.0, 1.0 - rescue_chance))
        rescue_roll = rng.random()
    if rescue_roll < rescue_chance:
        char.injury_status = "serious"
        rescuer = allies_at_loc[0] if allies_at_loc else None
        relation_tag_updates: List[Dict[str, str]] = []
        affected_characters = [char.char_id]
        rescue_source_id = None
        if rescuer:
            rescue_source_id = generate_record_id(rng)
            char.add_relation_tag(rescuer.char_id, "savior")
            rescuer.add_relation_tag(char.char_id, "rescued")
            relation_tag_updates = [
                {"source": char.char_id, "target": rescuer.char_id, "tag": "savior"},
                {"source": rescuer.char_id, "target": char.char_id, "tag": "rescued"},
            ]
            affected_characters.append(rescuer.char_id)
            desc = tr(
                "dying_rescued_by",
                name=char.name,
                rescuer=rescuer.name,
                location=world.location_name(char.location_id),
            )
        else:
            desc = tr(
                "dying_stabilized",
                name=char.name,
                location=world.location_name(char.location_id),
            )
        char.add_history(
            tr("history_narrowly_survived", year=world.year)
        )
        return EventResult(
            description=desc,
            affected_characters=affected_characters,
            event_type="dying_rescued",
            year=world.year,
            metadata={
                "relation_tag_updates": relation_tag_updates,
                **({"record_id": rescue_source_id} if rescue_source_id is not None else {}),
            },
        )
    if rescue_roll < rescue_chance + death_chance:
        return event_death(char, world, rng)
    return None
