"""Build NarrativeContext objects from world state."""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Optional

from ..reports import generate_yearly_report
from .context_models import NarrativeContext
from .context_relations import collect_relation_tags, normalize_observers

if TYPE_CHECKING:
    from ..character import Character
    from ..reports import YearlyReport
    from ..world import World


def build_narrative_context(
    world: "World",
    location_id: str,
    year: int,
    *,
    observer: Optional["Character" | Iterable["Character"]] = None,
    subject_id: Optional[str] = None,
    yearly_report: Optional["YearlyReport"] = None,
) -> NarrativeContext:
    """Build a minimal PR-I context from relation tags, reports, and world memory.

    Callers that need multiple contexts for the same year can pass a precomputed
    ``yearly_report`` to avoid repeating yearly aggregation work.
    """
    relation_tags = collect_relation_tags(observer, subject_id)
    observers = normalize_observers(observer)

    report = yearly_report if yearly_report is not None else generate_yearly_report(world, year)
    location_report = next(
        (entry for entry in report.location_entries if entry.location_id == location_id),
        None,
    )
    location = world.get_location_by_id(location_id)
    world_definition = world.setting_bundle.world_definition if world.setting_bundle is not None else None
    memorials = world.get_memorials_for_location(location_id)
    aliases = list(location.aliases) if location is not None else []
    traces = list(location.live_traces) if location is not None else []
    active_rumor_count = sum(
        1
        for rumor in world.rumors
        if rumor.source_location_id == location_id and not rumor.is_expired
    )
    subject_rumor_count = sum(
        1
        for rumor in world.rumors
        if (
            rumor.source_location_id == location_id
            and not rumor.is_expired
            and subject_id is not None
            and rumor.target_subject == subject_id
        )
    )
    notable_count = len(location_report.notable_events) if location_report is not None else 0
    return NarrativeContext(
        relation_tags=relation_tags,
        observer_count=len(observers),
        yearly_death_count=report.deaths_this_year,
        report_notable_count=notable_count,
        location_memorial_count=len(memorials),
        location_alias_count=len(aliases),
        location_trace_count=len(traces),
        location_rumor_count=active_rumor_count,
        subject_rumor_count=subject_rumor_count,
        world_definition_key=world_definition.world_key if world_definition is not None else "",
        world_display_name=world_definition.display_name if world_definition is not None else world.name,
        world_era=world_definition.era if world_definition is not None else "",
        location_region_type=location.region_type if location is not None else "",
    )
