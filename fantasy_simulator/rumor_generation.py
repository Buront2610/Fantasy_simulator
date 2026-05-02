"""Rumor generation and description building."""

from __future__ import annotations

import random
import uuid
from typing import TYPE_CHECKING, Any, List, Optional

from .event_rendering import render_event_record
from .i18n import tr
from .narrative.constants import EVENT_KINDS_FATAL
from .rumor_constants import DISCLOSURE, MIN_SEVERITY_FOR_RUMOR, RUMOR_BASE_CHANCE
from .rumor_models import Rumor

if TYPE_CHECKING:
    from .event_models import WorldEventRecord
    from .world import World


def _determine_reliability(
    event_severity: int,
    same_location: bool,
    months_elapsed: int,
    rng: Any = random,
) -> str:
    """Determine rumor reliability based on event properties and distance.

    Higher severity events produce more reliable rumors.
    Being at the same location increases reliability.
    Time degradation lowers reliability.
    """
    base_score = event_severity * 20  # 1->20, 5->100
    if same_location:
        base_score += 30
    base_score -= months_elapsed * 5
    base_score += rng.randint(-10, 10)

    if base_score >= 80:
        return "certain"
    if base_score >= 50:
        return "plausible"
    if base_score >= 20:
        return "doubtful"
    return "false"


def _category_from_event_kind(kind: str) -> str:
    """Map event kind to rumor category."""
    categories = {
        "death": "death",
        "battle_fatal": "battle",
        "battle": "battle",
        "marriage": "social",
        "discovery": "discovery",
        "journey": "movement",
        "adventure_started": "adventure",
        "adventure_discovery": "adventure",
        "adventure_death": "adventure",
        "adventure_returned": "adventure",
        "adventure_returned_injured": "adventure",
    }
    return categories.get(kind, "event")


def _content_tags_from_event(record: "WorldEventRecord") -> List[str]:
    """Extract content tags from an event record."""
    tags: List[str] = [record.kind]
    if record.severity >= 4:
        tags.append("major")
    if record.kind in EVENT_KINDS_FATAL:
        tags.append("tragic")
    if record.kind in ("marriage", "anniversary"):
        tags.append("social")
    if record.kind in ("discovery", "adventure_discovery"):
        tags.append("treasure")
    return tags


def _generate_misinformation(
    record: "WorldEventRecord",
    rng: Any = random,
) -> str:
    """Generate misleading content for a false reliability rumor.

    False rumors replace the actual event with plausible but incorrect info.
    """
    false_templates = [
        "rumor_false_wrong_actor",
        "rumor_false_wrong_location",
        "rumor_false_wrong_outcome",
        "rumor_false_exaggerated",
    ]
    template_key = rng.choice(false_templates)
    return tr(template_key, kind=record.kind)


def _build_rumor_description(
    record: "WorldEventRecord",
    reliability: str,
    world: "World",
    rng: Any = random,
) -> str:
    """Build a rumor description applying per-field disclosure masking.

    Each dimension is independently rolled against its disclosure probability.
    When any field is masked, a category-specific template naturally omits the
    hidden information instead of contradicting itself.
    """
    disclosure = DISCLOSURE[reliability]
    rendered_description = render_event_record(record, world=world)

    if reliability == "false":
        if rng.random() < disclosure["what"]:
            return rendered_description
        return _generate_misinformation(record, rng=rng)

    who_known = rng.random() < disclosure["who"]
    what_known = rng.random() < disclosure["what"]
    where_known = rng.random() < disclosure["where"]
    when_known = rng.random() < disclosure["when"]

    if who_known and what_known and where_known and when_known:
        return rendered_description

    if not what_known:
        return tr("rumor_vague_event")

    if who_known and record.primary_actor_id:
        char = world.get_character_by_id(record.primary_actor_id)
        who = char.name if char else tr("rumor_someone")
    else:
        who = tr("rumor_someone")

    if where_known and record.location_id:
        where = world.location_name(record.location_id)
    else:
        where = tr("rumor_somewhere")

    when = tr("rumor_recently") if when_known else tr("rumor_at_some_point")

    category = _category_from_event_kind(record.kind)
    template_key = f"rumor_heard_{category}"
    return tr(template_key, who=who, where=where, when=when)


def _months_elapsed_for_rumor(
    record: "WorldEventRecord",
    current_year: int,
    current_month: int,
    current_absolute_day: int,
    world: Optional["World"],
) -> tuple[int, Any]:
    period_calendar: Any
    if current_absolute_day > 0 and record.absolute_day > 0 and world is not None:
        period_calendar = world.calendar_definition_for_date(current_year, current_month)
        months_elapsed = world.months_elapsed_between(
            record.year,
            record.month,
            current_year,
            current_month,
            start_day=record.day,
            end_day=period_calendar.days_in_month(current_month),
            start_calendar_key=record.calendar_key,
        )
        return months_elapsed, period_calendar

    period_calendar = world.calendar_definition_for_date(current_year, current_month) if world is not None else None
    if world is not None:
        months_elapsed = world.months_elapsed_between(
            record.year,
            record.month,
            current_year,
            current_month,
            start_calendar_key=record.calendar_key,
        )
    else:
        months_elapsed = max(0, ((current_year - record.year) * 12) + (current_month - record.month))
    return months_elapsed, period_calendar


def generate_rumor_from_event(
    record: "WorldEventRecord",
    listener_location_id: Optional[str],
    current_year: int,
    current_month: int,
    current_absolute_day: int = 0,
    world: Optional["World"] = None,
    rng: Any = random,
) -> Optional[Rumor]:
    """Attempt to generate a rumor from a WorldEventRecord.

    Returns None if the event doesn't qualify or the random check fails.
    """
    if record.severity < MIN_SEVERITY_FOR_RUMOR:
        return None

    severity_bonus = 0.25 if record.severity >= 4 else (0.10 if record.severity >= 3 else 0.0)
    chance = min(RUMOR_BASE_CHANCE + severity_bonus, 1.0)
    if rng.random() > chance:
        return None

    same_location = listener_location_id is not None and record.location_id == listener_location_id
    months_elapsed, period_calendar = _months_elapsed_for_rumor(
        record,
        current_year,
        current_month,
        current_absolute_day,
        world,
    )
    reliability = _determine_reliability(
        record.severity, same_location, months_elapsed, rng=rng,
    )

    if world is not None:
        description = _build_rumor_description(record, reliability, world, rng=rng)
    else:
        description = render_event_record(record)

    if hasattr(rng, "getrandbits"):
        rumor_id = f"rum_{rng.getrandbits(48):012x}"
    else:
        rumor_id = f"rum_{uuid.uuid4().hex[:12]}"

    return Rumor(
        id=rumor_id,
        category=_category_from_event_kind(record.kind),
        source_location_id=record.location_id,
        target_subject=record.primary_actor_id or "",
        reliability=reliability,
        spread_level=min(record.severity, 5),
        age_in_months=months_elapsed,
        content_tags=_content_tags_from_event(record),
        description=description,
        source_event_id=record.record_id,
        year_created=current_year,
        month_created=current_month,
        created_absolute_day=current_absolute_day,
        created_calendar_key=(
            period_calendar.calendar_key if period_calendar is not None else record.calendar_key
        ),
    )


def generate_rumors_for_period(
    world: "World",
    year: int,
    month: int,
    listener_location_id: Optional[str] = None,
    max_rumors: int = 5,
    rng: Any = random,
) -> List[Rumor]:
    """Generate rumors from recent events for a given period.

    Scans events within the lookback window ending at *month*, filtering
    by severity and random chance. The default 12-month window ensures
    yearly batch generation captures events from the entire year.
    """
    lookback_months = world.months_per_year
    cutoff_year = year
    cutoff_month = month - lookback_months
    while cutoff_month < 1:
        cutoff_month += world.months_per_year
        cutoff_year -= 1

    candidates: List[WorldEventRecord] = []
    cutoff_abs = cutoff_year * world.months_per_year + cutoff_month
    current_abs = year * world.months_per_year + month
    current_absolute_day = world.latest_absolute_day_before_or_on(year, month)
    for record in world.event_records:
        event_abs = record.year * world.months_per_year + record.month
        if cutoff_abs <= event_abs <= current_abs and record.severity >= MIN_SEVERITY_FOR_RUMOR:
            candidates.append(record)

    candidates.sort(
        key=lambda record: (
            -record.absolute_day,
            -(record.year * world.months_per_year + record.month),
            -record.severity,
        )
    )

    existing_event_ids = {rumor.source_event_id for rumor in world.rumors}
    existing_event_ids.update(rumor.source_event_id for rumor in world.rumor_archive)

    rumors: List[Rumor] = []
    for record in candidates:
        if record.record_id in existing_event_ids:
            continue
        rumor = generate_rumor_from_event(
            record,
            listener_location_id,
            year,
            month,
            current_absolute_day=current_absolute_day,
            world=world,
            rng=rng,
        )
        if rumor is not None:
            rumors.append(rumor)
        if len(rumors) >= max_rumors:
            break

    return rumors
