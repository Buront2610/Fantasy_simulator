"""Event recording with ``world.event_records`` as the sole write model.

``world.event_records`` is the canonical structured store by policy.
All new read-paths should consume ``world.event_records`` exclusively.

``world.event_log`` and ``simulator.history`` survive only as compatibility
adapters projected from canonical records for legacy query paths. Save/load
keeps backward compatibility for older snapshots, but new snapshots persist
canonical records only.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..adventure import AdventureRun
from ..event_models import EventResult, WorldEventRecord, generate_record_id


class EventRecorderMixin:
    """Mixin providing event recording methods for the Simulator.

    Expected attributes on *self* (provided by ``engine.Simulator``):
    - ``world``: the World instance
    - ``current_month``: current in-world month (1–12)
    - ``current_day``: current in-world day (1–30)
    - ``elapsed_days``: absolute in-world days elapsed since simulation start
    - ``id_rng``: RNG for generating record IDs
    - ``pending_notifications``: list of records that passed notification threshold
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
        """Record a structured world event to canonical ``event_records``.

        Legacy ``event_log`` / ``history`` adapters are projected later from
        the stored canonical records.
        """
        effective_month = self.current_month if month is None else month
        effective_day = self.current_day
        record = WorldEventRecord(
            record_id=generate_record_id(self.id_rng),
            kind=kind,
            year=self.world.year if year is None else year,
            month=effective_month,
            day=effective_day,
            absolute_day=self.elapsed_days + 1,
            location_id=location_id,
            primary_actor_id=primary_actor_id,
            secondary_actor_ids=[] if secondary_actor_ids is None else list(secondary_actor_ids),
            description=description,
            severity=severity,
            visibility=visibility,
            calendar_key=self.world.calendar_definition.calendar_key,
        )
        record = self.world.record_event(record)
        # Apply event impact on location state and record causal impacts
        impacts = self.world.apply_event_impact(kind, record.location_id)
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
    def _classify_adventure_summary(
        previous_state: str, run: AdventureRun,
    ) -> Tuple[str, str, int]:
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
        """Mirror an EventResult into the canonical structured store."""
        severity = self._SEVERITY_MAP.get(result.event_type, 1)
        record = WorldEventRecord.from_event_result(
            result,
            location_id=location_id,
            severity=severity,
            record_id=result.metadata.get("record_id"),
            rng=self.id_rng,
            month=self.current_month,
            day=self.current_day,
            absolute_day=self.elapsed_days + 1,
            calendar_key=self.world.calendar_definition.calendar_key,
        )
        record = self.world.record_event(record)
        impacts = self.world.apply_event_impact(result.event_type, record.location_id)
        if impacts:
            record.impacts = impacts
        if self.should_notify(record):
            self.pending_notifications.append(record)
        self._link_relation_tag_source_from_record(result, record.record_id)
