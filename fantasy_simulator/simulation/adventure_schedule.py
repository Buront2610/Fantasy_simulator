"""Apply scheduled time, resource limits and next-day planning on a draft only."""

from typing import Any

from ..adventure.results import AdventureStepResult, step_fact_result
from ..i18n import tr


def prepare_scheduled_step(run: Any, tick: int) -> AdventureStepResult | None:
    schedule = run.schedule
    if schedule is None:
        return None
    schedule.settle(tick, len(run.member_ids))
    ratio = schedule.provisions / schedule.initial_provisions
    run.supply_state = "critical" if ratio <= 0.2 else "low" if ratio <= 0.5 else "full"
    if run.state in ("returning", "resolved"):
        return None
    if tick < schedule.deadline_tick and schedule.provisions > 0:
        return None
    reason = "deadline" if tick >= schedule.deadline_tick else "supplies"
    run.pending_choice = None
    run.state = "returning"
    schedule.segment_mode = "standard"
    text = tr("summary_adventure_schedule_retreat", name=run.character_name, reason=tr(f"adventure.limit_{reason}"))
    run._record(text, text)
    return step_fact_result(
        run, "adventure_retreat_started", "summary_adventure_schedule_retreat",
        {"name": run.character_name, "reason": tr(f"adventure.limit_{reason}"), "limit": reason},
        location_id=run.itinerary.current_site_id if run.itinerary is not None else None,
    )
