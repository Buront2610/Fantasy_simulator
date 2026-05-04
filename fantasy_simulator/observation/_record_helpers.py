"""Shared helpers for headless WorldEventRecord projections."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.world_event_index import location_ids_for_record


def as_string(value: Any) -> str | None:
    """Return a non-empty string payload, preserving saved textual IDs."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def string_param(record: WorldEventRecord, *keys: str) -> str | None:
    """Return the first non-empty string from record render params."""
    for key in keys:
        value = as_string(record.render_params.get(key))
        if value is not None:
            return value
    return None


def strings_from_value(value: Any) -> tuple[str, ...]:
    """Return all non-empty strings from a scalar or list-like payload."""
    if isinstance(value, list):
        return tuple(item for item in (as_string(raw) for raw in value) if item is not None)
    value_string = as_string(value)
    return (value_string,) if value_string is not None else ()


def string_params(record: WorldEventRecord, *keys: str) -> tuple[str, ...]:
    """Return unique non-empty strings from one or more render-param values."""
    values: list[str] = []
    for key in keys:
        for value in strings_from_value(record.render_params.get(key)):
            if value not in values:
                values.append(value)
    return tuple(values)


def impact_value(
    record: WorldEventRecord,
    *,
    value_key: str,
    attributes: Iterable[str] = (),
    target_type: str | None = None,
    target_id: str | None = None,
) -> Any:
    """Return the first impact value matching the supplied semantic filters."""
    attribute_set = set(attributes)
    for impact in record.impacts:
        if target_type is not None and impact.get("target_type") != target_type:
            continue
        if target_id is not None and impact.get("target_id") != target_id:
            continue
        if attribute_set and impact.get("attribute") not in attribute_set:
            continue
        if value_key in impact:
            return impact[value_key]
    return None


def impact_string(
    record: WorldEventRecord,
    *,
    value_key: str,
    attributes: Iterable[str] = (),
    target_type: str | None = None,
    target_id: str | None = None,
) -> str | None:
    """Return a string impact value matching the supplied semantic filters."""
    return as_string(
        impact_value(
            record,
            value_key=value_key,
            attributes=attributes,
            target_type=target_type,
            target_id=target_id,
        )
    )


def record_location_ids(record: WorldEventRecord) -> tuple[str, ...]:
    """Return all known location IDs attached to a record."""
    return tuple(location_ids_for_record(record))


def first_record_location_id(record: WorldEventRecord) -> str | None:
    """Return the first known location ID attached to a record."""
    return next(iter(record_location_ids(record)), None)


def semantic_render_params(record: WorldEventRecord) -> dict[str, Any]:
    """Return a projection-safe copy of semantic render params."""
    return deepcopy(record.render_params)
