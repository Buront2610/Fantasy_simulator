"""Rescue decisions on the closed adventure draft, never on the live world."""

from dataclasses import replace
from typing import Any

from .results import AdventureStepResult, step_fact_result
from ..i18n import tr


def _fact(world: Any, run: Any, kind: Any, reason: str = "") -> AdventureStepResult:
    goal = run.objective
    target = world.get_character_by_id(goal.target_id)
    result = step_fact_result(
        run, kind, f"summary_{kind}",
        {"name": run.character_name, "target": target.name,
         "reason": tr(f"adventure.reason_{reason}") if reason else "",
         "reason_key": f"adventure.reason_{reason}" if reason else "", "target_id": target.char_id},
        location_id=run.itinerary.current_site_id, severity=3 if kind == "adventure_rescued" else 1,
    )
    fact = result.facts[0]
    roles = {**fact.render_params["participant_roles"], target.char_id: "rescue_target"}
    fact = replace(fact, secondary_actor_ids=tuple(dict.fromkeys([*fact.secondary_actor_ids, target.char_id])),
                   cause_event_ids=tuple(dict.fromkeys([*fact.cause_event_ids,
                                                       *([goal.evidence_event_id] if goal.evidence_event_id else [])])),
                   render_params={**fact.render_params, "participant_roles": roles})
    run._record(fact.description, fact.description)
    return replace(result, facts=(fact,), summaries=(fact.description,))


def reassess_rescue(world: Any, run: Any) -> AdventureStepResult | None:
    goal = run.objective
    if goal is None or goal.purpose != "rescue" or goal.status != "active" or run.state == "returning":
        return None
    target = world.get_character_by_id(goal.target_id)
    place = world.presence[target.char_id]
    reason = ""
    if not target.alive:
        reason = "dead"
    elif target.active_adventure_id not in (None, goal.source_adventure_id):
        reason = "claimed"
    elif target.injury_status not in ("serious", "dying"):
        reason = "recovered"
    elif place is None:
        reason = "moving"
    elif goal.source_adventure_id and target.active_adventure_id is None and place == world.rescue_origin:
        reason = "returned"
    if reason:
        goal.status, goal.reason = "invalidated", reason
        run.pending_choice, run.state = None, "returning"
        return _fact(world, run, "adventure_objective_invalidated", reason)
    if place != run.destination:
        run.destination = place
        run.itinerary.visited_destination = place == run.itinerary.current_site_id
        run.pending_choice, run.state = None, "traveling"
        return _fact(world, run, "adventure_target_moved")
    return None


def _detach_target(world: Any, run: Any, target: Any) -> None:
    if not target.active_adventure_id:
        return
    source = world.get_adventure_by_id(target.active_adventure_id)
    if source.schedule is not None:
        source.schedule.settle(world.tick, len(source.member_ids))
    world.source_changed = True
    source.member_ids.remove(target.char_id)
    if not source.member_ids:
        # Keep the completed run's historical membership, but stop its old return plan.
        source.member_ids = [target.char_id]
        source.state, source.outcome, source.resolution_year = "resolved", "rescued", world.year
        source.pending_choice = None
        if source.objective is not None and source.objective.status == "active":
            source.objective.status = "failed"
        source._clear_member_adventures(world)
        return
    source.state, source.pending_choice = "returning", None
    if source.character_id == target.char_id:
        leader = world.get_character_by_id(source.member_ids[0])
        source.character_id, source.character_name = leader.char_id, leader.name
    if source.injury_member_id == target.char_id:
        source.injury_member_id, source.injury_status = None, "none"


def perform_rescue(world: Any, run: Any) -> AdventureStepResult | None:
    goal = run.objective
    if goal is None or goal.purpose != "rescue":
        return None
    target = world.get_character_by_id(goal.target_id)
    if goal.status != "active" or world.presence[target.char_id] != run.itinerary.current_site_id:
        raise ValueError("Rescue requires a live objective and physical colocation")
    cost = 2 * run.schedule.interval_days
    if run.schedule.provisions < cost:
        goal.status, goal.reason = "failed", "supplies"
        run.state = "returning"
        return _fact(world, run, "adventure_objective_invalidated", "supplies")
    run.schedule.provisions -= cost
    target.injury_status = {"dying": "serious", "serious": "injured"}[target.injury_status]
    _detach_target(world, run, target)
    target.active_adventure_id = run.adventure_id
    run.member_ids.append(target.char_id)
    target.location_id = run.itinerary.current_site_id
    for member_id in run.member_ids:
        if member_id != target.char_id:
            world.get_character_by_id(member_id).update_mutual_relationship(target, 15)
    goal.status, run.state, run.pending_choice = "rescued", "returning", None
    result = _fact(world, run, "adventure_rescued")
    for member_id in run.member_ids:
        world.get_character_by_id(member_id).add_history(result.facts[0].description)
    return result


def finalize_objective(world: Any, run: Any) -> None:
    goal = run.objective
    if goal is None or not run.is_resolved:
        return
    if goal.purpose == "rescue" and goal.status == "rescued":
        target = world.get_character_by_id(goal.target_id)
        goal.status = "completed" if target.alive and target.location_id == run.origin else "failed"
    elif goal.status == "active":
        goal.status = "completed" if goal.purpose == "explore" and run.loot_summary else "failed"
