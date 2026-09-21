"""Hazard resolution for adventure progression."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .results import AdventureStepResult, step_fact_result
from .combat import resolve_adventure_hazard_combat
from .rewards import ward_injury, drop_casualty_assets
from ..character_model.death_resolution import mark_character_dead
from ..i18n import tr

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World


def resolve_hazard_band(
    run: Any,
    injured_member: "Character",
    leader: "Character",
    world: "World",
    rng: Any,
    destination_name: str,
) -> AdventureStepResult:
    if injured_member.injury_status == "dying":
        run.outcome = "death"
        run.state = "resolved"
        run.resolution_year = world.year
        mark_character_dead(injured_member, world)
        run.death_member_id = injured_member.char_id
        leader.active_adventure_id = None
        run._clear_member_adventures(world)
        summary = tr("summary_adventure_died", name=injured_member.name, destination=destination_name)
        detail = tr("detail_adventure_died", name=injured_member.name, destination=destination_name)
        run._record(summary, detail)
        injured_member.add_history(tr("history_adventure_detail", year=world.year, detail=detail))
        return step_fact_result(run, "adventure_death", "summary_adventure_died",
                                {"name": injured_member.name, "destination": destination_name},
                                actor_id=injured_member.char_id, severity=5)

    hazard_result = resolve_adventure_hazard_combat(run, injured_member, world, rng)
    return resolve_nonfatal_adventure_injury(
        run,
        injured_member,
        destination_name,
        severity_steps=hazard_result.severity_steps,
        hazard_name=hazard_result.hazard_name,
        combat_rounds=hazard_result.rounds,
        world=world,
    )


def resolve_critical_hazard(
    run: Any,
    injured_member: "Character",
    world: "World",
    rng: Any,
    destination_name: str,
) -> AdventureStepResult:
    hazard_result = resolve_adventure_hazard_combat(run, injured_member, world, rng)
    severity_steps = hazard_result.severity_steps
    if hazard_result.member_lost and severity_steps > 0:
        severity_steps = max(3, severity_steps)
    return resolve_nonfatal_adventure_injury(
        run,
        injured_member,
        destination_name,
        severity_steps=severity_steps,
        hazard_name=hazard_result.hazard_name,
        combat_rounds=hazard_result.rounds,
        world=world,
    )


def resolve_nonfatal_adventure_injury(
    run: Any,
    injured_member: "Character",
    destination_name: str,
    *,
    severity_steps: int = 1,
    hazard_name: str | None = None,
    combat_rounds: int | None = None,
    world: Any = None,
) -> AdventureStepResult:
    asset_details: dict[str, Any] = {}
    if world is not None:
        severity_steps, asset_details = ward_injury(world, run, injured_member, severity_steps)
    previous_injury = injured_member.injury_status
    for _ in range(max(0, severity_steps)):
        if injured_member.injury_status == "dying":
            break
        injured_member.worsen_injury()
    if severity_steps > 0:
        run.injury_status = injured_member.injury_status
        run.injury_member_id = injured_member.char_id
        summary = tr("summary_adventure_injured", name=injured_member.name)
        detail = tr("detail_adventure_injured", name=injured_member.name, destination=destination_name)
    else:
        summary = tr("summary_adventure_hazard_unharmed", name=injured_member.name, destination=destination_name)
        detail = summary
    if hazard_name is not None and combat_rounds is not None:
        detail += " " + tr(
            "detail_adventure_hazard_combat",
            name=injured_member.name,
            hazard=hazard_name,
            destination=destination_name,
            rounds=combat_rounds,
        )
    if world is not None:
        dropped = drop_casualty_assets(world, run, injured_member, severity_steps)
        if dropped:
            asset_details.setdefault("asset_operations", []).extend(dropped)
        if asset_details.get("ward_artifact_id"):
            detail += " " + tr("assets.ward_used", name=injured_member.name)
    run._record(summary, detail)
    run.state = "returning"
    return step_fact_result(
        run, "adventure_injured" if severity_steps > 0 else "adventure_encounter",
        "summary_adventure_injured" if severity_steps > 0 else "summary_adventure_hazard_unharmed",
        {"name": injured_member.name, "destination": destination_name,
         "previous_injury": previous_injury, "injury_status": injured_member.injury_status,
         "hazard_name": hazard_name, "combat_rounds": combat_rounds, **asset_details},
        actor_id=injured_member.char_id, severity=3 if severity_steps > 0 else 2,
    )
