"""Nominal string IDs used by PR-K world-change contracts."""

from __future__ import annotations

from typing import NewType


CharacterId = NewType("CharacterId", str)
LocationId = NewType("LocationId", str)
RouteId = NewType("RouteId", str)
TerrainCellId = NewType("TerrainCellId", str)
FactionId = NewType("FactionId", str)
EventRecordId = NewType("EventRecordId", str)
EraKey = NewType("EraKey", str)
CultureId = NewType("CultureId", str)


__all__ = [
    "CharacterId",
    "LocationId",
    "RouteId",
    "TerrainCellId",
    "FactionId",
    "EventRecordId",
    "EraKey",
    "CultureId",
]
