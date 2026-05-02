"""Text presenters for Simulator query methods."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from ..event_models import WorldEventRecord
from ..event_rendering import render_event_record
from ..i18n import tr, tr_term
from ..narrative.constants import EVENT_KINDS_FATAL


def render_simulation_summary(
    *,
    world_name: str,
    year: int,
    total_events: int,
    alive_count: int,
    deceased_count: int,
    type_counts: Dict[str, int],
    records: Iterable[WorldEventRecord],
    world: Any = None,
) -> str:
    """Render the public simulation summary text."""
    lines = [
        "=" * 60,
        f"  {tr('summary_title', world=world_name)}",
        f"  {tr('final_year')}: {year}",
        "=" * 60,
        f"  {tr('total_events'):<22}: {total_events}",
        f"  {tr('characters_alive'):<22}: {alive_count}",
        f"  {tr('characters_deceased'):<22}: {deceased_count}",
        "",
        f"  {tr('event_breakdown')}:",
    ]
    for event_type, count in sorted(type_counts.items(), key=lambda item: -item[1]):
        i18n_key = f"event_type_{event_type}"
        localized_type = tr(i18n_key)
        if localized_type == i18n_key:
            localized_type = event_type.replace("_", " ").capitalize()
        lines.append(f"    {localized_type:<20} {count:>4} {tr('times_suffix')}")

    lines.append("")
    lines.append(f"  {tr('notable_moments')}:")
    dramatic = [
        record for record in records
        if record.kind in EVENT_KINDS_FATAL or record.kind in {"marriage", "discovery"}
    ]
    shown = dramatic[:5] if len(dramatic) >= 5 else dramatic
    for record in shown:
        lines.append(f"    • {render_event_record(record, world=world)}")

    lines.append("=" * 60)
    return "\n".join(lines)


def render_character_story(
    *,
    name: str,
    race: str,
    job: str,
    entries: List[str],
    stat_block: str,
) -> str:
    """Render one character's public life story text."""
    lines = [
        "─" * 50,
        f"  {tr('story_of', name=name)}",
        f"  {tr_term(race)} {tr_term(job)}",
        "─" * 50,
    ]
    if entries:
        for entry in entries:
            lines.append(f"  • {entry}")
    else:
        lines.append(f"  {tr('no_notable_events')}")

    lines.append("")
    lines.append(stat_block)
    lines.append("─" * 50)
    return "\n".join(lines)
