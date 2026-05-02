"""Structural protocols for small world helper modules."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import List, Protocol

from .event_models import WorldEventRecord
from .terrain import AtlasLayout, RouteEdge, Site, TerrainMap


class EventLogWorld(Protocol):
    """World attributes needed by the compatibility event-log facade."""

    MAX_EVENT_LOG: int
    year: int
    _display_event_log: List[str]

    @property
    def event_records(self) -> Sequence[WorldEventRecord]: ...


class MutableEventLogWorld(EventLogWorld, Protocol):
    """Event-log facade contract for helpers that update display entries."""

    _display_event_log: List[str]


class TopologyRuntimeWorld(Protocol):
    """World attributes needed when applying reconstructed topology state."""

    terrain_map: TerrainMap | None
    sites: List[Site]
    routes: Iterable[RouteEdge]
    _route_graph_explicit: bool
    atlas_layout: AtlasLayout | None

    def _rebuild_site_index(self) -> None: ...

    def _rebuild_route_index(self) -> None: ...


class RouteIndexChangeHandler(Protocol):
    """Callback used by observable route collections."""

    def __call__(self) -> None: ...
