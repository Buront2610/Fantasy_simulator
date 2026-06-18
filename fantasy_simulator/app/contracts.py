"""JSON-safe view models returned by the headless AppService."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True, slots=True)
class EventSummaryView:
    record_id: str
    kind: str
    year: int
    month: int
    day: int
    description: str
    severity: int
    actor_ids: List[str] = field(default_factory=list)
    location_id: Optional[str] = None
    cause_event_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class WorldDashboardSnapshot:
    world_name: str
    year: int
    month: int
    day: int
    elapsed_days: int
    alive_count: int
    deceased_count: int
    active_adventure_count: int
    pending_choice_count: int
    event_counts_by_kind: Dict[str, int]
    recent_events: List[EventSummaryView]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AppCommandResult:
    ok: bool
    command: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
