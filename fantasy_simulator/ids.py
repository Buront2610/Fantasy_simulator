"""Nominal string IDs used by PR-K world-change contracts."""

from __future__ import annotations

from typing import Callable, Iterable, NewType, TypeVar


CharacterId = NewType("CharacterId", str)
LocationId = NewType("LocationId", str)
RouteId = NewType("RouteId", str)
TerrainCellId = NewType("TerrainCellId", str)
FactionId = NewType("FactionId", str)
EventRecordId = NewType("EventRecordId", str)
EraKey = NewType("EraKey", str)
CultureId = NewType("CultureId", str)


TId = TypeVar("TId")


def normalize_required_id(value: object, *, field_name: str, id_type: Callable[[str], TId]) -> TId:
    """Normalize a required nominal ID at a command or adapter boundary."""
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return id_type(normalized)


def normalize_optional_id(value: object | None, *, id_type: Callable[[str], TId]) -> TId | None:
    """Normalize an optional nominal ID, treating blank values as absent."""
    if value is None:
        return None
    normalized = str(value).strip()
    return id_type(normalized) if normalized else None


def normalize_id_sequence(
    values: Iterable[object],
    *,
    field_name: str,
    id_type: Callable[[str], TId],
) -> tuple[TId, ...]:
    """Normalize required IDs while preserving first-seen order and dropping duplicates."""
    normalized_values = []
    for value in values:
        normalized = normalize_required_id(value, field_name=field_name, id_type=id_type)
        if normalized not in normalized_values:
            normalized_values.append(normalized)
    return tuple(normalized_values)


def terrain_cell_id_for_coords(x: int, y: int) -> TerrainCellId:
    """Return the canonical terrain-cell ID for grid coordinates."""
    return TerrainCellId(f"terrain:{x}:{y}")


__all__ = [
    "CharacterId",
    "LocationId",
    "RouteId",
    "TerrainCellId",
    "FactionId",
    "EventRecordId",
    "EraKey",
    "CultureId",
    "normalize_required_id",
    "normalize_optional_id",
    "normalize_id_sequence",
    "terrain_cell_id_for_coords",
]
