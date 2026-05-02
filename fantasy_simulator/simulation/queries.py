"""Summary, report, story, and event-log access for the Simulator.

``world.event_records`` is the canonical data source by policy.  New
read-paths should query ``event_records`` (via ``events_by_kind()``).

``history`` and ``event_log`` remain runtime compatibility adapters projected
from canonical records for legacy consumers. Older snapshots that still carry
legacy fields remain load-compatible.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..event_models import EventResult, WorldEventRecord
from ..event_rendering import render_event_record
from ..i18n import tr
from ..reports import (
    format_monthly_report,
    format_yearly_report,
    generate_monthly_report,
    generate_yearly_report,
)
from ..location_observation import (
    build_location_observation_view,
    build_rumor_summary_views,
    render_query_location_observation_sections,
    render_rumor_brief,
)
from .query_presenters import render_character_story, render_simulation_summary


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

        return render_simulation_summary(
            world_name=self.world.name,
            year=self.world.year,
            total_events=total,
            alive_count=alive,
            deceased_count=dead,
            type_counts=type_counts,
            records=records,
            world=self.world,
        )

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

    def get_active_rumors(
        self,
        location_id: Optional[str] = None,
        *,
        include_archive: bool = False,
        limit: Optional[int] = None,
    ) -> List[str]:
        """Return formatted rumor lines, optionally filtered to one location."""
        return [
            render_rumor_brief(rumor)
            for rumor in build_rumor_summary_views(
                self.world,
                location_id=location_id,
                include_archive=include_archive,
                limit=limit,
            )
        ]

    def get_location_observation(self, location_id: str) -> str:
        """Return an inspectable local observation summary for one location."""
        try:
            observation = build_location_observation_view(
                self.world,
                location_id,
                include_empty_traces=True,
            )
        except ValueError:
            return tr("map_detail_not_found", location=location_id)
        return "\n".join(render_query_location_observation_sections(observation))

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

        event_history = sorted(
            self.world.get_events_by_actor(char_id),
            key=lambda record: (
                record.year,
                record.month,
                record.day,
                record.absolute_day == 0,
                record.absolute_day,
                record.record_id,
            ),
        )
        seen_entries = set()
        story_entries: List[str] = []
        if event_history:
            for record in event_history:
                rendered = render_event_record(record, world=self.world)
                story_entries.append(rendered)
                seen_entries.add(rendered)
                seen_entries.add(record.description)
            for entry in char.history:
                if entry in seen_entries:
                    continue
                story_entries.append(entry)
        elif char.history:
            for entry in char.history:
                story_entries.append(entry)

        char_name_lookup = {world_char.char_id: world_char.name for world_char in self.world.characters}
        return render_character_story(
            name=char.name,
            race=char.race,
            job=char.job,
            entries=story_entries,
            stat_block=char.stat_block(
                char_name_lookup=char_name_lookup,
                location_resolver=self.world.location_name,
            ),
        )

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
        from the world's derived canonical event index when available.
        """
        if hasattr(self.world, "get_events_by_kind"):
            return self.world.get_events_by_kind(kind)
        return [rec for rec in self.world.event_records if rec.kind == kind]
