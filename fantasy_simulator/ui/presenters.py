"""Presenter layer for screen-friendly formatting.

Keeps text composition out of screen orchestration functions.
"""

from __future__ import annotations

from typing import List

from ..i18n import tr
from .view_models import (
    AdventureSummaryView,
    LocationHistoryView,
    LocationObservationView,
    MonthlyReportCardView,
    RumorSummaryView,
)


class AdventurePresenter:
    @staticmethod
    def render_summary_row(index: int, view: AdventureSummaryView) -> str:
        loot = f" | {tr('loot_label')}: {', '.join(view.loot)}" if view.loot else ""
        injury = f" | {tr('injury_label')}: {view.injury}" if view.injury != "none" else ""
        policy = f" [{tr('party_marker')}] ({tr('party_policy_short', policy=view.policy)})" if view.policy else ""
        return f"  {index:>2}. {view.title}{policy} | {view.origin} -> {view.destination} | {view.status}{injury}{loot}"


class LocationPresenter:
    @staticmethod
    def render_location_row(index: int, view: LocationHistoryView) -> str:
        tags = []
        if view.memorials:
            tags.append(tr("location_memorials_count", count=len(view.memorials)))
        if view.aliases:
            tags.append(tr("location_aliases_count", count=len(view.aliases)))
        if view.traces:
            tags.append(tr("location_traces_count", count=len(view.traces)))
        if view.recent_event_count:
            tags.append(tr("location_recent_events_count", count=view.recent_event_count))
        tag_str = f"  [{', '.join(tags)}]" if tags else ""
        return f"  {index:>2}. {view.location_name} ({view.region_type}){tag_str}"

    @staticmethod
    def render_observation_sections(view: LocationObservationView) -> List[str]:
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
                lines.append(f"    - {RumorPresenter.render_brief(rumor)}")
        return lines


class RumorPresenter:
    @staticmethod
    def render_brief(view: RumorSummaryView) -> str:
        reliability = tr(f"rumor_reliability_{view.reliability}")
        return f"{view.description} ({reliability})"


class ReportPresenter:
    @staticmethod
    def render_monthly_card(card: MonthlyReportCardView) -> List[str]:
        lines = [tr("monthly_report_card_header", year=card.year, month=card.month_label or card.month)]
        if card.highlighted_characters:
            lines.append(tr("monthly_report_card_characters", names=", ".join(card.highlighted_characters)))
        if card.highlighted_locations:
            lines.append(tr("monthly_report_card_locations", names=", ".join(card.highlighted_locations)))
        if card.completed_adventures:
            lines.append(tr("monthly_report_card_adventures", items=" | ".join(card.completed_adventures)))
        if card.new_memory_items:
            lines.append(tr("monthly_report_card_memory", items=" | ".join(card.new_memory_items)))
        if card.hot_rumors:
            lines.append(f"  {tr('report_section_rumors')}: {' | '.join(card.hot_rumors)}")
        return lines
