"""Route graph helpers for ``World``.

This module isolates route observer wiring and adjacency indexing from the
aggregate so ``World`` can delegate cache maintenance.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Mapping

from .terrain import RouteEdge, Site


class ObservableRouteList(list[RouteEdge]):
    """Route collection that invalidates cached adjacency on mutation."""

    def __init__(self, iterable=(), *, on_change: Callable[[], None] | None = None):
        super().__init__(iterable)
        self._on_change = on_change

    def _notify(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def __delitem__(self, index: Any) -> None:
        super().__delitem__(index)
        self._notify()

    def __iadd__(self, other: Iterable[RouteEdge]) -> "ObservableRouteList":
        result = super().__iadd__(other)
        self._notify()
        return result

    def __imul__(self, value: int) -> "ObservableRouteList":
        result = super().__imul__(value)
        self._notify()
        return result

    def __setitem__(self, index: Any, value: Any) -> None:
        super().__setitem__(index, value)
        self._notify()

    def append(self, value: RouteEdge) -> None:
        super().append(value)
        self._notify()

    def extend(self, iterable: Iterable[RouteEdge]) -> None:
        super().extend(iterable)
        self._notify()

    def insert(self, index: int, value: RouteEdge) -> None:
        super().insert(index, value)
        self._notify()

    def pop(self, index: int = -1) -> RouteEdge:
        value = super().pop(index)
        self._notify()
        return value

    def remove(self, value: RouteEdge) -> None:
        super().remove(value)
        self._notify()

    def clear(self) -> None:
        super().clear()
        self._notify()


def replace_routes(
    current_routes: Iterable[RouteEdge],
    new_routes: Iterable[RouteEdge],
    *,
    on_change: Callable[[], None],
) -> ObservableRouteList:
    """Replace the active route collection and detach stale observers."""
    for route in current_routes:
        route._on_change = None
    wrapped = ObservableRouteList(list(new_routes), on_change=on_change)
    attach_route_observers(wrapped, on_change=on_change)
    return wrapped


def attach_route_observers(routes: Iterable[RouteEdge], *, on_change: Callable[[], None]) -> None:
    """Attach mutation hooks to each route in the active collection."""
    for route in routes:
        route._on_change = on_change


def rebuild_route_index(
    *,
    sites: Iterable[Site],
    routes: Iterable[RouteEdge],
    on_change: Callable[[], None],
) -> Dict[str, List[RouteEdge]]:
    """Build route adjacency lists keyed by endpoint location ID."""
    site_list = list(sites)
    route_list = list(routes)
    attach_route_observers(route_list, on_change=on_change)
    route_index: Dict[str, List[RouteEdge]] = {site.location_id: [] for site in site_list}
    for route in route_list:
        route_index.setdefault(route.from_site_id, []).append(route)
        route_index.setdefault(route.to_site_id, []).append(route)
    return route_index


def routes_for_site(
    route_index: Mapping[str, List[RouteEdge]],
    location_id: str,
) -> List[RouteEdge]:
    """Return all cached routes connected to a site."""
    return list(route_index.get(location_id, []))
