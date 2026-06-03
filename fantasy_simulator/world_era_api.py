"""Transient PR-K era/civilization runtime API methods."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, MutableMapping, Optional

from .event_models import WorldEventRecord
from .ids import EraKey, EventRecordId
from .world_change import (
    DriftCivilizationPhaseCommand,
    ShiftEraCommand,
    apply_world_change_set,
    build_civilization_phase_drift_change_set,
    build_era_shift_change_set,
)

if TYPE_CHECKING:
    from .world_location_state import LocationState
    from .world_route_graph import RouteCollection


@dataclass
class _TransientEraRuntime:
    era_key: str
    civilization_phase: str
    world_scores: MutableMapping[str, int] = field(
        default_factory=lambda: {
            "prosperity": 50,
            "safety": 50,
            "traffic": 50,
            "mood": 50,
        }
    )


def _setting_entry_key(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_").replace("'", "")


class WorldEraMixin:
    """Non-persistent PR-K era/civilization runtime API methods."""

    if TYPE_CHECKING:
        year: int
        event_records: List[WorldEventRecord]
        routes: RouteCollection
        MAX_LIVE_TRACES: int
        _location_id_index: Dict[str, LocationState]

        def _world_change_description(
            self,
            *,
            summary_key: str,
            render_params: Dict[str, Any],
            fallback_description: str,
        ) -> str: ...

        def world_change_event_recorder(self) -> Any: ...

    def _current_era_key_from_setting_bundle(self) -> str:
        bundle = getattr(self, "_setting_bundle", None)
        world_definition = getattr(bundle, "world_definition", None)
        era_name = getattr(world_definition, "era", "")
        return _setting_entry_key(era_name) if isinstance(era_name, str) and era_name.strip() else "age_of_embers"

    def _world_era_runtime(self) -> _TransientEraRuntime:
        runtime = getattr(self, "_era_runtime", None)
        if isinstance(runtime, _TransientEraRuntime):
            return runtime
        from .observation import build_era_timeline_projection

        projection = build_era_timeline_projection(event_records=self.event_records)
        runtime = _TransientEraRuntime(
            era_key=projection.current_era_id or self._current_era_key_from_setting_bundle(),
            civilization_phase=projection.current_civilization_phase or "stable",
        )
        self._era_runtime = runtime
        return runtime

    def apply_era_shift(
        self,
        new_era_key: str,
        *,
        new_civilization_phase: str = "new_era",
        authored_era_keys: Optional[Iterable[str]] = None,
        year: Optional[int] = None,
        month: int = 1,
        day: int = 1,
        calendar_key: str = "",
        cause_key: str = "",
        cause_event_id: Optional[str] = None,
    ) -> WorldEventRecord | None:
        """Shift the transient era runtime and record a canonical world-change event."""
        runtime = self._world_era_runtime()
        known_era_keys = (
            {runtime.era_key, new_era_key}
            if authored_era_keys is None
            else {str(era_key) for era_key in authored_era_keys}
        )
        command = ShiftEraCommand(
            new_era_key=EraKey(new_era_key),
            new_civilization_phase=new_civilization_phase,
            year=self.year if year is None else year,
            month=month,
            day=day,
            calendar_key=calendar_key,
            cause_key=cause_key,
            cause_event_id=None if cause_event_id is None else EventRecordId(cause_event_id),
        )

        def _describe(summary_key: str, render_params: Dict[str, Any], fallback_description: str) -> str:
            return self._world_change_description(
                summary_key=summary_key,
                render_params=render_params,
                fallback_description=fallback_description,
            )

        change_set = build_era_shift_change_set(
            command,
            era_runtime=runtime,
            authored_era_keys=known_era_keys,
            describe=_describe,
        )
        if change_set is None:
            return None
        stored_records = apply_world_change_set(
            change_set,
            routes=self.routes,
            era_runtime=runtime,
            record_event=self.world_change_event_recorder(),
        )
        if not stored_records:
            return None
        from .world_conflict_pressure import apply_era_pressure_to_locations

        apply_era_pressure_to_locations(
            stored_records[0],
            location_index=self._location_id_index,
            max_live_traces=self.MAX_LIVE_TRACES,
            world_context=self,
        )
        return stored_records[0]

    def apply_civilization_phase_drift(
        self,
        new_phase: str,
        *,
        score_deltas: Optional[Dict[str, int]] = None,
        year: Optional[int] = None,
        month: int = 1,
        day: int = 1,
        calendar_key: str = "",
        reason_key: str = "",
        cause_event_id: Optional[str] = None,
    ) -> WorldEventRecord | None:
        """Drift transient civilization phase/scores and record a canonical world-change event."""
        runtime = self._world_era_runtime()
        command = DriftCivilizationPhaseCommand(
            new_phase=new_phase,
            score_deltas={} if score_deltas is None else dict(score_deltas),
            year=self.year if year is None else year,
            month=month,
            day=day,
            calendar_key=calendar_key,
            reason_key=reason_key,
            cause_event_id=None if cause_event_id is None else EventRecordId(cause_event_id),
        )

        def _describe(summary_key: str, render_params: Dict[str, Any], fallback_description: str) -> str:
            return self._world_change_description(
                summary_key=summary_key,
                render_params=render_params,
                fallback_description=fallback_description,
            )

        change_set = build_civilization_phase_drift_change_set(
            command,
            era_runtime=runtime,
            describe=_describe,
        )
        if change_set is None:
            return None
        stored_records = apply_world_change_set(
            change_set,
            routes=self.routes,
            era_runtime=runtime,
            record_event=self.world_change_event_recorder(),
        )
        if not stored_records:
            return None
        from .world_conflict_pressure import apply_civilization_pressure_to_locations

        apply_civilization_pressure_to_locations(
            stored_records[0],
            location_index=self._location_id_index,
            max_live_traces=self.MAX_LIVE_TRACES,
            world_context=self,
        )
        return stored_records[0]
