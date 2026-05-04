"""Headless era and civilization timeline projection from event records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from fantasy_simulator.event_models import WorldEventRecord

from ._record_helpers import as_string, semantic_render_params, string_param


@dataclass(frozen=True)
class EraTimelineEntry:
    """An era or civilization change summarized for observation."""

    record_id: str
    kind: str
    year: int
    month: int
    day: int
    old_era_id: str | None
    new_era_id: str | None
    old_civilization_phase: str | None
    new_civilization_phase: str | None
    description: str
    summary_key: str = ""
    render_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EraTimelineProjection:
    """Read model for era shifts and civilization phase drift."""

    entries: tuple[EraTimelineEntry, ...]
    current_era_id: str | None
    current_civilization_phase: str | None


def _is_era_or_civilization_record(record: WorldEventRecord) -> bool:
    kind = record.kind.casefold()
    return (
        kind.startswith("era_")
        or kind.startswith("civilization_")
        or kind.startswith("civilisation_")
        or "era_shift" in kind
        or "civilization" in kind
        or "civilisation" in kind
    )


def _impact_transition(record: WorldEventRecord, *attributes: str) -> tuple[str | None, str | None]:
    attribute_set = set(attributes)
    old_value: str | None = None
    new_value: str | None = None
    for impact in record.impacts:
        if impact.get("attribute") not in attribute_set:
            continue
        old_value = old_value or as_string(impact.get("old_value"))
        new_value = new_value or as_string(impact.get("new_value"))
    return old_value, new_value


def _entry_from_record(record: WorldEventRecord) -> EraTimelineEntry | None:
    old_era_id = string_param(record, "old_era_id", "old_era_key", "old_era")
    new_era_id = string_param(record, "new_era_id", "new_era_key", "new_era", "era_id", "era_key", "era")
    old_civilization_phase = string_param(
        record,
        "old_civilization_phase",
        "old_civilisation_phase",
        "old_civilization_id",
        "old_civilisation_id",
    )
    new_civilization_phase = string_param(
        record,
        "new_civilization_phase",
        "new_civilisation_phase",
        "civilization_phase",
        "civilisation_phase",
        "new_civilization_id",
        "new_civilisation_id",
        "civilization_id",
        "civilisation_id",
    )

    impact_old_era, impact_new_era = _impact_transition(record, "era_id", "era_key", "era")
    impact_old_civ, impact_new_civ = _impact_transition(
        record,
        "civilization_phase",
        "civilisation_phase",
        "civilization_id",
        "civilisation_id",
    )
    old_era_id = old_era_id or impact_old_era
    new_era_id = new_era_id or impact_new_era
    old_civilization_phase = old_civilization_phase or impact_old_civ
    new_civilization_phase = new_civilization_phase or impact_new_civ

    if (
        old_era_id is None
        and new_era_id is None
        and old_civilization_phase is None
        and new_civilization_phase is None
    ):
        return None

    return EraTimelineEntry(
        record_id=record.record_id,
        kind=record.kind,
        year=record.year,
        month=record.month,
        day=record.day,
        old_era_id=old_era_id,
        new_era_id=new_era_id,
        old_civilization_phase=old_civilization_phase,
        new_civilization_phase=new_civilization_phase,
        description=record.description,
        summary_key=record.summary_key,
        render_params=semantic_render_params(record),
    )


def build_era_timeline_projection(
    *,
    event_records: Iterable[WorldEventRecord],
) -> EraTimelineProjection:
    """Build an era/civilization read model using only canonical event records."""
    entries: list[EraTimelineEntry] = []
    current_era_id: str | None = None
    current_civilization_phase: str | None = None

    for record in event_records:
        if not _is_era_or_civilization_record(record):
            continue
        entry = _entry_from_record(record)
        if entry is None:
            continue
        entries.append(entry)
        if entry.new_era_id is not None:
            current_era_id = entry.new_era_id
        if entry.new_civilization_phase is not None:
            current_civilization_phase = entry.new_civilization_phase

    return EraTimelineProjection(
        entries=tuple(entries),
        current_era_id=current_era_id,
        current_civilization_phase=current_civilization_phase,
    )
