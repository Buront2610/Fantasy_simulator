"""
rumor.py - Rumor system for the Fantasy Simulator.

Rumors are generated from WorldEventRecord entries and spread through
the world with varying reliability.  They give players indirect,
imperfect information about events they did not directly observe.

Rumor reliability levels (SI-7):
  certain   - confirmed first-hand information
  plausible - likely true, minor details may be off
  doubtful  - unreliable, missing or wrong details
  false     - misinformation, key facts replaced

Design reference: docs/next_version_plan.md §11
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from i18n import tr

if TYPE_CHECKING:
    from events import WorldEventRecord
    from world import World

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

RELIABILITY_LEVELS = ("certain", "plausible", "doubtful", "false")

DISCLOSURE: Dict[str, Dict[str, float]] = {
    "certain":   {"who": 1.0, "what": 1.0, "where": 1.0, "when": 1.0},
    "plausible": {"who": 0.9, "what": 0.8, "where": 0.7, "when": 0.5},
    "doubtful":  {"who": 0.5, "what": 0.6, "where": 0.3, "when": 0.2},
    "false":     {"who": 0.3, "what": 0.0, "where": 0.5, "when": 0.1},
}

# Minimum severity for an event to spawn a rumor
_MIN_SEVERITY_FOR_RUMOR = 2

# Base probability of generating a rumor from a qualifying event
_RUMOR_BASE_CHANCE = 0.6

# Maximum number of active rumors per world
MAX_ACTIVE_RUMORS = 50

# Months before a rumor expires
RUMOR_MAX_AGE_MONTHS = 24


# ------------------------------------------------------------------
# Rumor dataclass
# ------------------------------------------------------------------

@dataclass
class Rumor:
    """A piece of information circulating in the world.

    Rumors are derived from WorldEventRecord entries but may have
    degraded reliability depending on distance and time elapsed.
    """

    id: str = field(default_factory=lambda: f"rum_{uuid.uuid4().hex[:12]}")
    category: str = "event"
    source_location_id: Optional[str] = None
    target_subject: str = ""
    reliability: str = "plausible"
    spread_level: int = 1
    age_in_months: int = 0
    content_tags: List[str] = field(default_factory=list)
    description: str = ""
    source_event_id: Optional[str] = None
    year_created: int = 0
    month_created: int = 1

    def __post_init__(self) -> None:
        if self.reliability not in RELIABILITY_LEVELS:
            self.reliability = "plausible"
        self.spread_level = max(0, min(10, self.spread_level))
        self.age_in_months = max(0, self.age_in_months)

    @property
    def is_expired(self) -> bool:
        return self.age_in_months >= RUMOR_MAX_AGE_MONTHS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "source_location_id": self.source_location_id,
            "target_subject": self.target_subject,
            "reliability": self.reliability,
            "spread_level": self.spread_level,
            "age_in_months": self.age_in_months,
            "content_tags": list(self.content_tags),
            "description": self.description,
            "source_event_id": self.source_event_id,
            "year_created": self.year_created,
            "month_created": self.month_created,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Rumor":
        return cls(
            id=data.get("id", f"rum_{uuid.uuid4().hex[:12]}"),
            category=data.get("category", "event"),
            source_location_id=data.get("source_location_id"),
            target_subject=data.get("target_subject", ""),
            reliability=data.get("reliability", "plausible"),
            spread_level=data.get("spread_level", 1),
            age_in_months=data.get("age_in_months", 0),
            content_tags=list(data.get("content_tags", [])),
            description=data.get("description", ""),
            source_event_id=data.get("source_event_id"),
            year_created=data.get("year_created", 0),
            month_created=data.get("month_created", 1),
        )


# ------------------------------------------------------------------
# Rumor generation
# ------------------------------------------------------------------

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


def _content_tags_from_event(record: WorldEventRecord) -> List[str]:
    """Extract content tags from an event record."""
    tags: List[str] = [record.kind]
    if record.severity >= 4:
        tags.append("major")
    if record.kind in ("death", "battle_fatal", "adventure_death"):
        tags.append("tragic")
    if record.kind in ("marriage", "anniversary"):
        tags.append("social")
    if record.kind in ("discovery", "adventure_discovery"):
        tags.append("treasure")
    return tags


def _generate_misinformation(
    record: WorldEventRecord,
    rng: Any = random,
) -> str:
    """Generate misleading content for a 'false' reliability rumor (§11.4).

    False rumors replace the actual event with plausible but incorrect info.
    """
    _FALSE_TEMPLATES = [
        "rumor_false_wrong_actor",
        "rumor_false_wrong_location",
        "rumor_false_wrong_outcome",
        "rumor_false_exaggerated",
    ]
    template_key = rng.choice(_FALSE_TEMPLATES)
    return tr(template_key, kind=record.kind)


def _build_rumor_description(
    record: WorldEventRecord,
    reliability: str,
    world: World,
    rng: Any = random,
) -> str:
    """Build a rumor description applying per-field DISCLOSURE masking.

    Each dimension (who / what / where / when) is independently rolled
    against its disclosure probability.  When any field is masked, a
    category-specific template is used that naturally omits the hidden
    information — avoiding contradictions where the original description
    mentions a name or place that is then annotated as "unknown".

    Design reference: docs/next_version_plan.md §11.3
    """
    disclosure = DISCLOSURE[reliability]

    # "false" reliability: §11.4 — misinformation, not omission
    if reliability == "false":
        if rng.random() < disclosure["what"]:
            return record.description
        return _generate_misinformation(record, rng=rng)

    # Determine which fields are revealed
    who_known = rng.random() < disclosure["who"]
    what_known = rng.random() < disclosure["what"]
    where_known = rng.random() < disclosure["where"]
    when_known = rng.random() < disclosure["when"]

    # If all fields are known, return the original description
    if who_known and what_known and where_known and when_known:
        return record.description

    # If what is unknown, the core event detail is lost
    if not what_known:
        return tr("rumor_vague_event")

    # Resolve names: use actual values when disclosed, placeholders when masked
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

    # Select category-specific template
    category = _category_from_event_kind(record.kind)
    template_key = f"rumor_heard_{category}"
    return tr(template_key, who=who, where=where, when=when)


def generate_rumor_from_event(
    record: WorldEventRecord,
    listener_location_id: Optional[str],
    current_year: int,
    current_month: int,
    world: Optional[World] = None,
    rng: Any = random,
) -> Optional[Rumor]:
    """Attempt to generate a rumor from a WorldEventRecord.

    Returns None if the event doesn't qualify or the random check fails.
    """
    if record.severity < _MIN_SEVERITY_FOR_RUMOR:
        return None

    # Higher severity events are more likely to spawn rumors.
    # severity 4+ gets a +0.25 bonus, severity 3 gets +0.10.
    severity_bonus = 0.25 if record.severity >= 4 else (0.10 if record.severity >= 3 else 0.0)
    chance = min(_RUMOR_BASE_CHANCE + severity_bonus, 1.0)
    if rng.random() > chance:
        return None

    same_location = (
        listener_location_id is not None
        and record.location_id == listener_location_id
    )
    months_elapsed = (current_year - record.year) * 12 + (current_month - record.month)
    months_elapsed = max(0, months_elapsed)

    reliability = _determine_reliability(
        record.severity, same_location, months_elapsed, rng=rng,
    )

    if world is not None:
        description = _build_rumor_description(record, reliability, world, rng=rng)
    else:
        # Fallback for callers that don't supply world (e.g. legacy tests)
        description = record.description

    rumor_id = f"rum_{rng.getrandbits(48):012x}" if hasattr(rng, 'getrandbits') else f"rum_{uuid.uuid4().hex[:12]}"
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
    )


def generate_rumors_for_period(
    world: World,
    year: int,
    month: int,
    listener_location_id: Optional[str] = None,
    max_rumors: int = 5,
    rng: Any = random,
) -> List[Rumor]:
    """Generate rumors from recent events for a given period.

    Scans events within the lookback window ending at *month*, filtering
    by severity and random chance.  The default 12-month window ensures
    that yearly batch generation (called at month 12) captures events
    from the entire year rather than only the final quarter.
    """
    lookback_months = 12
    cutoff_year = year
    cutoff_month = month - lookback_months
    while cutoff_month < 1:
        cutoff_month += 12
        cutoff_year -= 1

    candidates: List[WorldEventRecord] = []
    cutoff_abs = cutoff_year * 12 + cutoff_month
    current_abs = year * 12 + month
    for r in world.event_records:
        event_abs = r.year * 12 + r.month
        if cutoff_abs <= event_abs <= current_abs and r.severity >= _MIN_SEVERITY_FOR_RUMOR:
            candidates.append(r)

    # Prioritise recent, high-severity events so the rumor selection
    # reflects "what the world is talking about" rather than array order.
    # Use absolute month (year*12+month) so cross-year lookback sorts
    # correctly (e.g. prior-year Dec < current-year Jan).
    candidates.sort(key=lambda r: (-(r.year * 12 + r.month), -r.severity))

    existing_event_ids = {rum.source_event_id for rum in world.rumors}
    existing_event_ids.update(rum.source_event_id for rum in world.rumor_archive)

    rumors: List[Rumor] = []
    for record in candidates:
        if record.record_id in existing_event_ids:
            continue
        rumor = generate_rumor_from_event(
            record, listener_location_id, year, month, world=world, rng=rng,
        )
        if rumor is not None:
            rumors.append(rumor)
        if len(rumors) >= max_rumors:
            break

    return rumors


def age_rumors(
    rumors: List[Rumor], months: int = 1,
) -> tuple:
    """Age all rumors, returning (active, newly_expired).

    Expired rumors are separated so they can be archived for stable
    historical report generation.
    """
    active: List[Rumor] = []
    expired: List[Rumor] = []
    for rumor in rumors:
        rumor.age_in_months += months
        if rumor.is_expired:
            expired.append(rumor)
        else:
            active.append(rumor)
    return active, expired


def trim_rumors(
    rumors: List[Rumor], max_count: int = MAX_ACTIVE_RUMORS,
) -> tuple:
    """Keep only the most recent rumors up to max_count.

    Returns (kept, trimmed) so trimmed rumors can be archived.
    """
    if len(rumors) <= max_count:
        return rumors, []
    sorted_rumors = sorted(rumors, key=lambda r: r.age_in_months)
    return sorted_rumors[:max_count], sorted_rumors[max_count:]
