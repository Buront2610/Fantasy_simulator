"""Shared location observation view models and text rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, TYPE_CHECKING

from .i18n import tr, tr_term

if TYPE_CHECKING:
    from .world import World


@dataclass
class RumorSummaryView:
    rumor_id: str
    description: str
    reliability: str
    category: str = "event"
    source_location_id: str | None = None
    source_location_name: str = ""
    age_in_months: int = 0
    spread_level: int = 0


@dataclass
class LocationObservationView:
    location_id: str
    location_name: str
    region_type: str
    generated_endonym: str = ""
    aliases: List[str] = field(default_factory=list)
    memorials: List[str] = field(default_factory=list)
    traces: List[str] = field(default_factory=list)
    recent_events: List[str] = field(default_factory=list)
    connected_routes: List[str] = field(default_factory=list)
    rumors: List[RumorSummaryView] = field(default_factory=list)
    resident_names: List[str] = field(default_factory=list)


def build_rumor_summary_views(
    world: "World",
    *,
    location_id: str | None = None,
    include_archive: bool = False,
    limit: int | None = None,
) -> List[RumorSummaryView]:
    """Return rumor rows suitable for inspection UIs and query surfaces."""
    rumors = list(getattr(world, "rumors", []))
    if include_archive:
        rumors.extend(getattr(world, "rumor_archive", []))
    if location_id is not None:
        rumors = [rumor for rumor in rumors if rumor.source_location_id == location_id]
    rumors = [rumor for rumor in rumors if not rumor.is_expired]

    rumors.sort(
        key=lambda rumor: (
            rumor.age_in_months,
            -rumor.year_created,
            -rumor.month_created,
            rumor.id,
        )
    )
    if limit is not None:
        rumors = rumors[: max(0, limit)]

    return [
        RumorSummaryView(
            rumor_id=rumor.id,
            description=rumor.description,
            reliability=rumor.reliability,
            category=rumor.category,
            source_location_id=rumor.source_location_id,
            source_location_name=(
                world.location_name(rumor.source_location_id)
                if rumor.source_location_id
                else ""
            ),
            age_in_months=rumor.age_in_months,
            spread_level=rumor.spread_level,
        )
        for rumor in rumors
    ]


def build_location_observation_view(
    world: "World",
    location_id: str,
    *,
    rumor_limit: int = 3,
    event_limit: int = 5,
    route_limit: int = 5,
) -> LocationObservationView:
    """Return an inspectable snapshot of one location's current local context."""
    location = world.get_location_by_id(location_id)
    if location is None:
        raise ValueError(f"Unknown location id: {location_id}")

    memorials = [
        tr("memorial_entry", year=memorial.year, epitaph=memorial.epitaph)
        for memorial in world.get_memorials_for_location(location_id)
    ]
    traces = [
        trace.get("text", "")
        for trace in reversed(location.live_traces[-event_limit:])
        if trace.get("text")
    ]

    record_lookup = {record.record_id: record for record in getattr(world, "event_records", [])}
    recent_events = [
        tr("location_recent_event_entry", year=record.year, description=record.description)
        for record_id in reversed(location.recent_event_ids[-event_limit:])
        for record in [record_lookup.get(record_id)]
        if record is not None
    ]

    route_summaries: List[str] = []
    for route in world.get_routes_for_site(location_id)[:route_limit]:
        other_location_id = route.to_site_id if route.from_site_id == location_id else route.from_site_id
        blocked = f" {tr('route_blocked')}" if route.blocked else ""
        route_summaries.append(
            f"{world.location_name(other_location_id)} ({tr_term(route.route_type)}){blocked}"
        )

    residents = [
        character.name
        for character in world.get_characters_at_location(location_id)
    ]

    return LocationObservationView(
        location_id=location.id,
        location_name=location.canonical_name,
        region_type=tr_term(location.region_type),
        generated_endonym=location.generated_endonym,
        aliases=list(location.aliases),
        memorials=memorials,
        traces=traces,
        recent_events=recent_events,
        connected_routes=route_summaries,
        rumors=build_rumor_summary_views(world, location_id=location_id, limit=rumor_limit),
        resident_names=residents[:event_limit],
    )


def render_rumor_brief(view: RumorSummaryView) -> str:
    reliability = tr(f"rumor_reliability_{view.reliability}")
    return f"{view.description} ({reliability})"


def render_location_observation_sections(view: LocationObservationView) -> List[str]:
    lines: List[str] = []
    if view.generated_endonym:
        lines.append(f"  {tr('location_endonym_label')}: {view.generated_endonym}")
        lines.append("")

    lines.append(f"  {tr('location_aliases_label')}:")
    if view.aliases:
        lines.append(f"    {', '.join(view.aliases)}")
    else:
        lines.append("    -")

    lines.append("")
    lines.append(f"  {tr('location_memorials_label')}:")
    if view.memorials:
        for memorial in view.memorials:
            lines.append(f"    {memorial}")
    else:
        lines.append(f"    {tr('no_memorials')}")

    lines.append("")
    lines.append(f"  {tr('location_live_traces_label')}:")
    if view.traces:
        for trace in view.traces:
            lines.append(f"    - {trace}")
    else:
        lines.append(f"    {tr('no_live_traces')}")

    lines.append("")
    lines.append(f"  {tr('location_recent_events_label')}:")
    if view.recent_events:
        for event in view.recent_events:
            lines.append(f"    - {event}")
    else:
        lines.append(f"    {tr('no_recent_events')}")

    if view.connected_routes:
        lines.append("")
        lines.append(f"  {tr('map_region_routes')}:")
        for route in view.connected_routes:
            lines.append(f"    - {route}")

    if view.rumors:
        lines.append("")
        lines.append(f"  {tr('rumor_section_title')}:")
        for rumor in view.rumors:
            lines.append(f"    - {render_rumor_brief(rumor)}")
    return lines
