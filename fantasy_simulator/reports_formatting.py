"""i18n-aware report formatting helpers."""

from __future__ import annotations

from .i18n import tr
from .reports_models import MonthlyReport, YearlyReport


def format_monthly_report(report: MonthlyReport) -> str:
    """Format a MonthlyReport as displayable text."""
    title = tr(
        "report_monthly_title",
        year=report.year,
        month=report.month_label or report.month,
        season=tr("season_" + report.season),
    )
    lines = [
        "=" * 55,
        f"  {title}",
        "=" * 55,
    ]

    if report.character_entries:
        lines.append("")
        lines.append(f"  {tr('report_section_watched')}")
        for entry in report.character_entries:
            lines.append(f"    {entry.name}")
            for event in entry.events:
                lines.append(f"      - {event}")

    if report.notable_events:
        lines.append("")
        lines.append(f"  {tr('report_section_notable')}")
        for event in report.notable_events:
            lines.append(f"    - {event}")

    if report.location_entries:
        lines.append("")
        lines.append(f"  {tr('report_section_world')}")
        for location in report.location_entries:
            if location.notable_events:
                for event in location.notable_events:
                    lines.append(f"    {location.name}: {event}")
            else:
                lines.append(
                    f"    {location.name}: {tr('report_location_activity', count=location.event_count)}"
                )

    if report.rumor_entries:
        lines.append("")
        lines.append(f"  {tr('report_section_rumors')}")
        for entry in report.rumor_entries:
            reliability_label = tr(f"rumor_reliability_{entry.reliability}")
            lines.append(f"    - {entry.description} ({reliability_label})")

    lines.append("")
    lines.append(f"  {tr('report_total_events', count=report.total_events)}")
    lines.append("=" * 55)
    return "\n".join(lines)


def format_yearly_report(report: YearlyReport) -> str:
    """Format a YearlyReport as displayable text."""
    lines = [
        "=" * 55,
        f"  {tr('report_yearly_title', year=report.year)}",
        "=" * 55,
    ]

    lines.append("")
    lines.append(f"  {tr('report_section_world_overview')}")
    lines.append(f"    {tr('total_events')}: {report.total_events}")
    if report.deaths_this_year:
        lines.append(f"    {tr('report_deaths_this_year', count=report.deaths_this_year)}")

    if report.notable_events:
        lines.append("")
        lines.append(f"  {tr('report_section_notable')}")
        for event in report.notable_events:
            lines.append(f"    - {event}")

    if report.location_entries:
        lines.append("")
        lines.append(f"  {tr('report_section_locations')}")
        for location in report.location_entries:
            if location.notable_events:
                for event in location.notable_events:
                    lines.append(f"    {location.name}: {event}")
            else:
                lines.append(
                    f"    {location.name}: {tr('report_location_activity', count=location.event_count)}"
                )

    if report.character_entries:
        lines.append("")
        lines.append(f"  {tr('report_section_watched_year')}")
        for entry in report.character_entries:
            if entry.events:
                summary = "; ".join(entry.events[:2])
                lines.append(f"    {entry.name}: {summary}")
            else:
                lines.append(f"    {entry.name}")

    lines.append("=" * 55)
    return "\n".join(lines)
