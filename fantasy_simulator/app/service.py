"""Headless application service around the simulation engine."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from typing import Any, Dict, List

from ..world_event.models import WorldEventRecord
from ..simulation import Simulator
from .contracts import AppCommandResult, EventSummaryView, WorldDashboardSnapshot


class FantasyAppService:
    """Small command/view boundary for non-CLI UI adapters."""

    def __init__(self, simulator: Simulator) -> None:
        self._simulator = simulator

    @property
    def simulator(self) -> Simulator:
        return self._simulator

    def dashboard(self, *, recent_event_limit: int = 10) -> WorldDashboardSnapshot:
        world = self._simulator.world
        alive_count = sum(1 for character in world.characters if character.alive)
        deceased_count = len(world.characters) - alive_count
        event_counts = Counter(record.kind for record in world.event_records)
        pending_choices = sum(1 for run in world.active_adventures if run.pending_choice is not None)
        recent_records = sorted(
            world.event_records,
            key=lambda record: (record.year, record.month, record.day, record.absolute_day, record.record_id),
            reverse=True,
        )[:max(0, recent_event_limit)]
        snapshot = WorldDashboardSnapshot(
            world_name=world.name,
            year=world.year,
            month=self._simulator.current_month,
            day=self._simulator.current_day,
            elapsed_days=self._simulator.elapsed_days,
            alive_count=alive_count,
            deceased_count=deceased_count,
            active_adventure_count=len(world.active_adventures),
            pending_choice_count=pending_choices,
            event_counts_by_kind=dict(sorted(event_counts.items())),
            recent_events=[_event_summary(record) for record in recent_records],
        )
        _assert_json_safe(snapshot.to_dict())
        return snapshot

    def handle_command(self, command: Mapping[str, Any]) -> AppCommandResult:
        command_name = _required_command_name(command)
        if command_name == "get_dashboard":
            return self._result(command_name, {"dashboard": self.dashboard().to_dict()})
        if command_name == "advance_years":
            years = _required_non_negative_int(command, "years")
            self._simulator.advance_years(years)
            return self._result(command_name, {"dashboard": self.dashboard().to_dict()})
        if command_name == "advance_days":
            days = _required_non_negative_int(command, "days")
            self._simulator.advance_days(days)
            return self._result(command_name, {"dashboard": self.dashboard().to_dict()})
        if command_name == "get_event_causes":
            record_id = _required_string(command, "record_id")
            causes = [_event_summary(record).to_dict() for record in self._simulator.world.get_event_causes(record_id)]
            effects = [
                _event_summary(record).to_dict()
                for record in self._simulator.world.get_events_caused_by(record_id)
            ]
            return self._result(command_name, {"record_id": record_id, "causes": causes, "effects": effects})
        raise ValueError(f"Unknown app command: {command_name!r}")

    def _result(self, command_name: str, data: Dict[str, Any]) -> AppCommandResult:
        result = AppCommandResult(ok=True, command=command_name, data=data)
        _assert_json_safe(result.to_dict())
        return result


def _event_summary(record: WorldEventRecord) -> EventSummaryView:
    actor_ids: List[str] = []
    if record.primary_actor_id:
        actor_ids.append(record.primary_actor_id)
    actor_ids.extend(record.secondary_actor_ids)
    return EventSummaryView(
        record_id=record.record_id,
        kind=record.kind,
        year=record.year,
        month=record.month,
        day=record.day,
        description=record.description,
        severity=record.severity,
        actor_ids=actor_ids,
        location_id=record.location_id,
        cause_event_ids=list(record.cause_event_ids),
    )


def _required_command_name(command: Mapping[str, Any]) -> str:
    return _required_string(command, "command")


def _required_string(command: Mapping[str, Any], field_name: str) -> str:
    value = command.get(field_name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _required_non_negative_int(command: Mapping[str, Any], field_name: str) -> int:
    value = command.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _assert_json_safe(payload: Dict[str, Any]) -> None:
    json.dumps(payload, ensure_ascii=False, sort_keys=True)
