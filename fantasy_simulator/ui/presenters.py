"""Presenter layer for screen-friendly formatting.

Keeps text composition out of screen orchestration functions.
"""

from __future__ import annotations

from typing import Any, List

from ..i18n import tr
from ..location_observation import (
    LocationObservationView,
    RumorSummaryView,
    render_location_observation_sections,
    render_rumor_brief,
)
from .view_models import (
    AdventureSummaryView,
    LocationHistoryView,
    MonthlyReportCardView,
    YearlyReportCardView,
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
        return render_location_observation_sections(view)


class RumorPresenter:
    @staticmethod
    def render_brief(view: RumorSummaryView) -> str:
        return render_rumor_brief(view)


class LanguagePresenter:
    @staticmethod
    def render_status(status: dict) -> List[str]:
        samples = status.get("sample_forms", {})
        lineage = " > ".join(status.get("lineage", []))
        lines = [
            f"  {status.get('display_name', status.get('language_key', ''))}",
            f"    {tr('language_lineage_label')}: {lineage}",
        ]
        runtime_state = status.get("runtime_state", {})
        derived_name_stems = LanguagePresenter._join_strings(runtime_state.get("derived_name_stems", []), limit=3)
        derived_toponym_suffixes = LanguagePresenter._join_strings(
            runtime_state.get("derived_toponym_suffixes", []),
            limit=3,
        )
        given_names = LanguagePresenter._join_strings(samples.get("given_names", []), limit=3)
        surnames = ", ".join(samples.get("surnames", []))
        lexicon = LanguagePresenter._join_strings(samples.get("lexicon", []), limit=5)
        sound_shifts = LanguagePresenter._format_sound_shifts(status.get("sound_shifts", {}), limit=4)
        if given_names:
            if derived_name_stems:
                given_names = f"{given_names} (+{derived_name_stems})"
            lines.append(f"    {tr('language_given_names_label')}: {given_names}")
        if surnames:
            lines.append(f"    {tr('language_surnames_label')}: {surnames}")
        if lexicon:
            lines.append(f"    {tr('language_lexicon_label')}: {lexicon}")
        if samples.get("toponym"):
            toponym = str(samples["toponym"])
            if derived_toponym_suffixes:
                toponym = f"{toponym} (+{derived_toponym_suffixes})"
            lines.append(f"    {tr('language_toponym_label')}: {toponym}")
        evolution_count = str(status.get("evolution_count", 0))
        if sound_shifts:
            evolution_count = f"{evolution_count} ({sound_shifts})"
        lines.append(
            f"    {tr('language_evolution_count_label')}: "
            f"{evolution_count}"
        )
        lines.extend(
            f"      {record_line}"
            for record_line in LanguagePresenter._format_recent_evolution_records(
                status.get("recent_evolution_records", []),
                limit=3,
            )
        )
        return lines

    @staticmethod
    def _join_strings(values: Any, *, limit: int) -> str:
        if not isinstance(values, list):
            return ""
        return ", ".join(str(value) for value in values[:limit] if str(value))

    @staticmethod
    def _format_sound_shifts(sound_shifts: Any, *, limit: int) -> str:
        if not isinstance(sound_shifts, dict):
            return ""
        shifts = [
            f"{source}>{target}"
            for source, target in sound_shifts.items()
            if str(source) and str(target)
        ]
        return ", ".join(shifts[:limit])

    @staticmethod
    def _format_recent_evolution_records(records: Any, *, limit: int) -> List[str]:
        if not isinstance(records, list):
            return []
        return [
            line
            for line in (
                LanguagePresenter._format_evolution_record(record)
                for record in reversed(records[-limit:])
            )
            if line
        ]

    @staticmethod
    def _format_evolution_record(record: Any) -> str:
        if not isinstance(record, dict):
            return ""
        year = str(record.get("year", "")).strip()
        changes = []
        source = str(record.get("source_token", "")).strip()
        target = str(record.get("target_token", "")).strip()
        if source:
            changes.append(f"{source}>{target}")
        name_stem = str(record.get("added_name_stem", "")).strip()
        if name_stem:
            changes.append(f"+{name_stem}")
        toponym_suffix = str(record.get("added_toponym_suffix", "")).strip()
        if toponym_suffix:
            changes.append(f"+{toponym_suffix}")
        if not changes:
            return ""
        rule_position = str(record.get("rule_position", "")).strip()
        detail = f" ({rule_position})" if rule_position and rule_position != "any" else ""
        prefix = f"{year}: " if year else ""
        return f"{prefix}{', '.join(changes)}{detail}"


class ReportPresenter:
    @staticmethod
    def render_monthly_card(card: MonthlyReportCardView) -> List[str]:
        lines = [tr("monthly_report_card_header", year=card.year, month=card.month_label or card.month)]
        if card.headline_events:
            lines.append(f"  {tr('report_section_headlines')}:")
            lines.extend(
                f"    {tr(f'report_headline_category_{headline.category}')}: {headline.text}"
                for headline in card.headline_events
            )
        if card.highlighted_characters:
            lines.append(tr("monthly_report_card_characters", names=", ".join(card.highlighted_characters)))
        if card.highlighted_locations:
            lines.append(tr("monthly_report_card_locations", names=", ".join(card.highlighted_locations)))
        if card.location_threads:
            lines.append(f"  {tr('report_section_location_threads')}:")
            lines.extend(
                tr(
                    "report_location_thread_line",
                    location=thread.location_name,
                    count=thread.event_count,
                    world_changes=thread.world_change_count,
                    headline=thread.headline,
                )
                for thread in card.location_threads
            )
        if card.completed_adventures:
            lines.append(tr("monthly_report_card_adventures", items=" | ".join(card.completed_adventures)))
        if card.new_memory_items:
            lines.append(tr("monthly_report_card_memory", items=" | ".join(card.new_memory_items)))
        if card.hot_rumors:
            lines.append(f"  {tr('report_section_rumors')}: {' | '.join(card.hot_rumors)}")
        if card.world_changes:
            summary = ", ".join(
                f"{tr(f'world_change_category_{change.category}')}: {change.count}"
                for change in card.world_changes
            )
            lines.append(f"  {tr('report_section_world')}: {summary}")
            lines.extend(
                f"    {tr(f'world_change_category_{entry.category}')}: {entry.text}"
                for entry in card.world_change_entries[:3]
            )
        return lines

    @staticmethod
    def render_yearly_card(card: YearlyReportCardView) -> List[str]:
        lines = [tr("yearly_report_card_header", year=card.year)]
        lines.append(tr("yearly_report_card_total_events", count=card.total_events))
        if card.headline_events:
            lines.append(f"  {tr('report_section_headlines')}:")
            lines.extend(
                f"    {tr(f'report_headline_category_{headline.category}')}: {headline.text}"
                for headline in card.headline_events
            )
        if card.highlighted_locations:
            lines.append(tr("monthly_report_card_locations", names=", ".join(card.highlighted_locations)))
        if card.location_threads:
            lines.append(f"  {tr('report_section_location_threads')}:")
            lines.extend(
                tr(
                    "report_location_thread_line",
                    location=thread.location_name,
                    count=thread.event_count,
                    world_changes=thread.world_change_count,
                    headline=thread.headline,
                )
                for thread in card.location_threads
            )
        if card.world_changes:
            summary = ", ".join(
                f"{tr(f'world_change_category_{change.category}')}: {change.count}"
                for change in card.world_changes
            )
            lines.append(f"  {tr('report_section_world')}: {summary}")
            lines.extend(
                f"    {tr(f'world_change_category_{entry.category}')}: {entry.text}"
                for entry in card.world_change_entries[:5]
            )
        return lines
