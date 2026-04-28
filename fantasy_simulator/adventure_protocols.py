"""Protocols shared by adventure helper modules."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, Protocol

if TYPE_CHECKING:
    from .world import World


class AdventureRunLike(Protocol):
    character_id: str
    character_name: str
    origin: str
    destination: str
    year_started: int
    adventure_id: str
    state: str
    injury_status: str
    steps_taken: int
    pending_choice: Any
    outcome: Optional[str]
    loot_summary: List[str]
    summary_log: List[str]
    detail_log: List[str]
    resolution_year: Optional[int]
    injury_member_id: Optional[str]
    death_member_id: Optional[str]
    member_ids: List[str]
    party_id: Optional[str]
    policy: str
    retreat_rule: str
    supply_state: str
    danger_level: int

    @property
    def is_resolved(self) -> bool:
        ...

    @property
    def is_party(self) -> bool:
        ...

    def _record(self, summary: str, detail: str) -> None:
        ...

    def _clear_member_adventures(self, world: "World") -> None:
        ...
