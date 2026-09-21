"""Validation helpers for adventure run payloads."""

from __future__ import annotations

from .constants import (
    ALL_POLICIES,
    ALL_RETREAT_RULES,
    SUPPLY_CRITICAL,
    SUPPLY_FULL,
    SUPPLY_LOW,
)
from .protocols import AdventureRunLike


def validate_adventure_run_payload(run: AdventureRunLike) -> None:
    validate_adventure_progress_state(run)
    validate_objective_state(run)
    if run.policy not in ALL_POLICIES:
        raise ValueError(f"policy must be one of {ALL_POLICIES}")
    if run.retreat_rule not in ALL_RETREAT_RULES:
        raise ValueError(f"retreat_rule must be one of {ALL_RETREAT_RULES}")
    if run.supply_state not in (SUPPLY_FULL, SUPPLY_LOW, SUPPLY_CRITICAL):
        raise ValueError("supply_state must be one of ('full', 'low', 'critical')")
    if not isinstance(run.danger_level, int) or isinstance(run.danger_level, bool):
        raise ValueError("danger_level must be an integer")
    if run.danger_level < 0 or run.danger_level > 100:
        raise ValueError("danger_level must be between 0 and 100")
    if not isinstance(run.member_ids, list) or any(not isinstance(member_id, str) for member_id in run.member_ids):
        raise ValueError("member_ids must be a list of strings")
    if run.member_ids and run.character_id not in run.member_ids:
        raise ValueError("member_ids must include character_id")
    if (
        not isinstance(run.related_event_ids, list)
        or any(not isinstance(record_id, str) for record_id in run.related_event_ids)
    ):
        raise ValueError("related_event_ids must be a list of strings")


def validate_adventure_progress_state(run: AdventureRunLike) -> None:
    if run.itinerary is not None:
        run.itinerary.validate()
        if run.schedule is None:
            raise ValueError("Physical itinerary requires a schedule")
        if run.itinerary.active_leg is not None and run.schedule.next_step_tick != run.itinerary.arrival_tick:
            raise ValueError("Travel arrival and next step must agree")
        if run.itinerary.active_leg is not None and run.state not in ("traveling", "returning"):
            raise ValueError("Active travel requires a travel state")
    if run.schedule is not None:
        run.schedule.__post_init__()


def validate_objective_state(run: AdventureRunLike) -> None:
    goal = run.objective
    if goal is None:
        return
    goal.validate()
    if goal.target_id == run.character_id or goal.source_adventure_id == run.adventure_id:
        raise ValueError("A rescuer cannot target themselves or their own expedition")
    if goal.purpose == "rescue":
        joined = goal.target_id in run.member_ids
        if goal.status in ("rescued", "completed") and not joined:
            raise ValueError("A rescued target must belong to the rescuing party")
        if goal.status == "active" and joined:
            raise ValueError("An active rescue target cannot already belong to the rescuing party")
