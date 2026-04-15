"""Summary, report, story, and event-log access for the Simulator.

``world.event_records`` is the canonical data source by policy.  New
read-paths should query ``event_records`` (via ``events_by_kind()``).

``history`` and ``event_log`` remain as compatibility adapters projected
from canonical records for legacy consumers and persisted save snapshots.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..event_models import EventResult, WorldEventRecord
from ..i18n import tr, tr_term
from ..narrative.constants import EVENT_KINDS_FATAL
from ..reports import (
    format_monthly_report,
    format_yearly_report,
    generate_monthly_report,
    generate_yearly_report,
)


class QueryMixin:
    """Mixin providing query / reporting methods for the Simulator.

    Expected attributes on *self* (provided by ``engine.Simulator``):
    - ``world``: the World instance
    - ``start_year``: baseline year for report bounds
    - ``history``: legacy EventResult list (compatibility adapter)
    """

    def get_summary(self) -> str:
        """Return a human-readable summary using WorldEventRecord as canonical source."""
        records = self.world.event_records
        total = len(records)
        alive = sum(1 for c in self.world.characters if c.alive)
        dead = sum(1 for c in self.world.characters if not c.alive)

        type_counts: Dict[str, int] = {}
        for rec in records:
            type_counts[rec.kind] = type_counts.get(rec.kind, 0) + 1

        lines = [
            "=" * 60,
            f"  {tr('summary_title', world=self.world.name)}",
            f"  {tr('final_year')}: {self.world.year}",
            "=" * 60,
            f"  {tr('total_events'):<22}: {total}",
            f"  {tr('characters_alive'):<22}: {alive}",
            f"  {tr('characters_deceased'):<22}: {dead}",
            "",
            f"  {tr('event_breakdown')}:",
        ]
        for etype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            i18n_key = f"event_type_{etype}"
            localized_type = tr(i18n_key)
            if localized_type == i18n_key:
                localized_type = etype.replace("_", " ").capitalize()
            lines.append(f"    {localized_type:<20} {count:>4} {tr('times_suffix')}")

        lines.append("")
        lines.append(f"  {tr('notable_moments')}:")
        dramatic = [
            rec for rec in records
            if rec.kind in EVENT_KINDS_FATAL or rec.kind in {"marriage", "discovery"}
        ]
        shown = dramatic[:5] if len(dramatic) >= 5 else dramatic
        for rec in shown:
            lines.append(f"    • {rec.description}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def get_monthly_report(self, year: int, month: int) -> str:
        """Generate and format a monthly report for the given year and month."""
        report = generate_monthly_report(self.world, year, month)
        return format_monthly_report(report)

    def get_yearly_report(self, year: int) -> str:
        """Generate and format a yearly report for the given year."""
        report = generate_yearly_report(self.world, year)
        return format_yearly_report(report)

    def get_latest_completed_report_year(self) -> int:
        """Return the latest year that should be used for end-of-year reports.

        Preference is "last completed year" (``world.year - 1``).  If the
        simulation has not completed even one full year yet, this falls back
        to the simulator baseline (``start_year``).
        """
        candidate = self.world.year - 1
        baseline = self.start_year
        if self.world.event_records:
            baseline = min(baseline, min(r.year for r in self.world.event_records))
        return max(candidate, baseline)

    def get_latest_yearly_report(self) -> str:
        """Generate and format a yearly report for the most recent completed year."""
        return self.get_yearly_report(self.get_latest_completed_report_year())

    def get_active_rumors(self) -> List[str]:
        """Return formatted strings for currently active rumors."""
        lines: List[str] = []
        for rumor in self.world.rumors:
            if rumor.is_expired:
                continue
            reliability_label = tr(f"rumor_reliability_{rumor.reliability}")
            lines.append(f"{rumor.description} ({reliability_label})")
        return lines

    def get_character_story(self, char_id: str) -> str:
        """Return the life story of a single character.

        Parameters
        ----------
        char_id : str
            The character's unique ID.
        """
        char = self.world.get_character_by_id(char_id)
        if char is None:
            return tr("no_character_found", char_id=char_id)

        lines = [
            "─" * 50,
            f"  {tr('story_of', name=char.name)}",
            f"  {tr_term(char.race)} {tr_term(char.job)}",
            "─" * 50,
        ]
        if char.history:
            for entry in char.history:
                lines.append(f"  • {entry}")
        else:
            lines.append(f"  {tr('no_notable_events')}")

        lines.append("")
        char_name_lookup = {world_char.char_id: world_char.name for world_char in self.world.characters}
        lines.append(
            char.stat_block(
                char_name_lookup=char_name_lookup,
                location_resolver=self.world.location_name,
            )
        )
        lines.append("─" * 50)
        return "\n".join(lines)

    def get_all_stories(self, only_alive: bool = False) -> str:
        """Return stories for all characters, optionally filtering to the living."""
        chars = self.world.characters
        if only_alive:
            chars = [c for c in chars if c.alive]
        return "\n\n".join(self.get_character_story(c.char_id) for c in chars)

    # ------------------------------------------------------------------
    # Event log access and compatibility adapters
    # ------------------------------------------------------------------

    def get_event_log(self, last_n: Optional[int] = None) -> List[str]:
        """Return the compatibility text log, optionally only the last *n*.

        Reads through ``World.get_compatibility_event_log()`` for backward
        compatibility. New features should query ``world.event_records``
        directly instead.
        """
        return self.world.get_compatibility_event_log(last_n=last_n)

    def events_by_type(self, event_type: str) -> List[EventResult]:
        """Return legacy EventResult entries of the given type.

        This compatibility adapter returns projected ``EventResult`` objects
        derived from the canonical store, so it now sees the full event set.
        Keep this only for migration-era callers; new code should call
        ``events_by_kind()``.
        """
        return [ev for ev in self.history if ev.event_type == event_type]

    def events_by_kind(self, kind: str) -> List[WorldEventRecord]:
        """Return WorldEventRecord entries matching the given kind.

        This is the canonical replacement for ``events_by_type()``, reading
        from ``world.event_records`` directly.  Linear scan is acceptable
        for typical simulation sizes (hundreds of records per run).
        """
        return [rec for rec in self.world.event_records if rec.kind == kind]
