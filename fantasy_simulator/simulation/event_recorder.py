"""Event recording across all transitional event stores.

During the Phase C migration, event recording writes to:
- ``world.event_records`` — the canonical structured store
- ``world.event_log`` — display-derived formatted text buffer
- ``simulator.history`` — compatibility cache of EventResult objects

New read-paths should consume ``world.event_records`` exclusively.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..adventure import AdventureRun
from ..events import EventResult, WorldEventRecord, generate_record_id


class EventRecorderMixin:
    """Mixin providing event recording methods for the Simulator.

    Expected attributes on *self* (provided by ``engine.Simulator``):
    - ``world``: the World instance
    - ``current_month``: current in-world month (1–12)
    - ``id_rng``: RNG for generating record IDs
    - ``pending_notifications``: list of records that passed notification threshold
    - ``history``: legacy EventResult list (compatibility adapter)
    """

    # Severity scale: 1=minor, 2=notable, 3=significant, 4=major, 5=critical
    _SEVERITY_MAP: Dict[str, int] = {
        "death": 5, "battle_fatal": 5, "marriage": 4,
        "discovery": 3, "battle": 3, "journey": 2,
        "meeting": 1, "aging": 1, "skill_training": 1,
        "romance": 2, "anniversary": 2,
        "condition_worsened": 3, "dying_rescued": 4,
    }

    def _record_world_event(
        self,
        description: str,
        *,
        kind: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
        location_id: Optional[str] = None,
        primary_actor_id: Optional[str] = None,
        secondary_actor_ids: Optional[List[str]] = None,
        severity: int = 1,
        visibility: str = "public",
    ) -> WorldEventRecord:
        """Record a structured world event and mirror it to the legacy text log."""
        effective_month = self.current_month if month is None else month
        self.world.log_event(description, month=effective_month)
        record = WorldEventRecord(
            record_id=generate_record_id(self.id_rng),
            kind=kind,
            year=self.world.year if year is None else year,
            month=effective_month,
            location_id=location_id,
            primary_actor_id=primary_actor_id,
            secondary_actor_ids=[] if secondary_actor_ids is None else list(secondary_actor_ids),
            description=description,
            severity=severity,
            visibility=visibility,
        )
        self.world.record_event(record)
        # Apply event impact on location state and record causal impacts
        impacts = self.world.apply_event_impact(kind, location_id)
        if impacts:
            record.impacts = impacts
        # Surface notable events to the UI layer via notification thresholds
        if self.should_notify(record):
            self.pending_notifications.append(record)
        return record

    def _link_relation_tag_source_from_record(self, result: EventResult, record_id: str) -> None:
        """Attach canonical WorldEventRecord IDs to relation tag sources."""
        updates = result.metadata.get("relation_tag_updates", [])
        for update in updates:
            source_id = update.get("source")
            target_id = update.get("target")
            tag = update.get("tag")
            if not source_id or not target_id or not tag:
                continue
            source_char = self.world.get_character_by_id(source_id)
            if source_char is None or not source_char.has_relation_tag(target_id, tag):
                continue
            source_char.add_relation_tag(target_id, tag, source_event_id=record_id)

    @staticmethod
    def _classify_adventure_summary(previous_state: str, run: AdventureRun) -> tuple:
        if previous_state == "traveling":
            return "adventure_arrived", run.destination, 2
        if previous_state == "waiting_for_choice":
            return "adventure_choice", run.destination, 1
        if previous_state == "exploring":
            if run.outcome == "death":
                return "adventure_death", run.destination, 5
            if run.state == "returning" and run.injury_status != "none":
                return "adventure_injured", run.destination, 3
            return "adventure_discovery", run.destination, 2
        if previous_state == "returning":
            if run.outcome == "injury":
                return "adventure_returned_injured", run.origin, 3
            if run.outcome == "safe_return":
                return "adventure_returned", run.origin, 2
            if run.outcome == "retreat":
                return "adventure_retreated", run.origin, 1
        return "adventure_update", run.destination, 1

    def _record_event(self, result: EventResult, location_id: Optional[str] = None) -> None:
        """Mirror an EventResult into all transitional event stores.

        During the Phase C migration:
        - ``history`` keeps the legacy EventResult view alive (compatibility adapter)
        - ``world.event_log`` keeps CLI-facing formatted strings alive (display-derived)
        - ``world.event_records`` is the canonical structured event history
        """
        self.history.append(result)
        severity = self._SEVERITY_MAP.get(result.event_type, 1)
        record = self._record_world_event(
            result.description,
            kind=result.event_type,
            year=result.year,
            location_id=location_id,
            primary_actor_id=result.affected_characters[0] if result.affected_characters else None,
            secondary_actor_ids=result.affected_characters[1:],
            severity=severity,
        )
        self._link_relation_tag_source_from_record(result, record.record_id)
