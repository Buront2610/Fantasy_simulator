"""Data models for narrative context selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from .context_relations import CLOSE_RELATION_TAGS, primary_relation_tag


@dataclass(frozen=True)
class NarrativeContext:
    """Narrative selection context derived from relations, reports, and memory."""

    relation_tags: Sequence[str] = field(default_factory=tuple)
    observer_count: int = 0
    yearly_death_count: int = 0
    report_notable_count: int = 0
    location_memorial_count: int = 0
    location_alias_count: int = 0
    location_trace_count: int = 0
    location_rumor_count: int = 0
    subject_rumor_count: int = 0
    world_definition_key: str = ""
    world_display_name: str = ""
    world_era: str = ""
    location_region_type: str = ""

    @property
    def primary_relation_tag(self) -> Optional[str]:
        return primary_relation_tag(self.relation_tags)

    @property
    def has_close_relation(self) -> bool:
        return any(tag in CLOSE_RELATION_TAGS for tag in self.relation_tags)

    @property
    def is_tragic_site(self) -> bool:
        return (
            self.yearly_death_count >= 2
            or self.report_notable_count >= 2
            or self.location_memorial_count >= 1
        )
