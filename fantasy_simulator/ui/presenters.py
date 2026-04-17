"""Presenter layer for screen-friendly formatting.

Keeps text composition out of screen orchestration functions.
"""

from __future__ import annotations

from typing import List

from ..i18n import tr
from .view_models import AdventureSummaryView, LocationHistoryView, MonthlyReportCardView


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
        return lines
