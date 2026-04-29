"""Route graph helpers for ``World``.

This module isolates route observer wiring and adjacency indexing from the
aggregate so ``World`` can delegate cache maintenance.
"""

from __future__ import annotations

from collections.abc import Iterable as IterableABC
from collections.abc import Iterator, MutableSequence
from typing import Callable, Dict, Iterable, List, Mapping, overload

from .terrain import RouteEdge, Site


class RouteCollection(MutableSequence[RouteEdge]):
    """Route collection that invalidates cached adjacency on mutation."""

    def __init__(
        self,
        routes: Iterable[RouteEdge] = (),
        *,
        on_change: Callable[[], None] | None = None,
    ) -> None:
        self._items: list[RouteEdge] = []
        self._on_change = on_change
        for route in routes:
            self._attach(route)
            self._items.append(route)

    def _notify(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def _attach(self, route: RouteEdge) -> None:
        current_callback = route._on_change
        if current_callback is not None and current_callback is not self._on_change:
            raise ValueError("RouteEdge instances cannot be shared across active RouteCollection owners")
        route._on_change = self._on_change

    @staticmethod
    def _validate_route(route: object) -> RouteEdge:
        if not isinstance(route, RouteEdge):
            raise TypeError("route collection entries must be RouteEdge instances")
        return route

    def _contains_identity(self, route: RouteEdge) -> bool:
        return any(item is route for item in self._items)

    def _detach_if_removed(self, route: RouteEdge) -> None:
        if not self._contains_identity(route):
            route._on_change = None

    @overload
    def __getitem__(self, index: int) -> RouteEdge:
        ...

    @overload
    def __getitem__(self, index: slice) -> list[RouteEdge]:
        ...

    def __getitem__(self, index: int | slice) -> RouteEdge | list[RouteEdge]:
        return self._items[index]

    @overload
    def __setitem__(self, index: int, value: RouteEdge) -> None:
        ...

    @overload
    def __setitem__(self, index: slice, value: Iterable[RouteEdge]) -> None:
        ...

    def __setitem__(self, index: int | slice, value: RouteEdge | Iterable[RouteEdge]) -> None:
        if isinstance(index, slice):
            if isinstance(value, RouteEdge) or not isinstance(value, IterableABC):
                raise TypeError("slice assignment requires an iterable of RouteEdge")
            old_routes = self._items[index]
            new_routes = [self._validate_route(route) for route in value]
            for route in new_routes:
                self._attach(route)
            self._items[index] = new_routes
            for route in old_routes:
                self._detach_if_removed(route)
            self._notify()
            return
        value = self._validate_route(value)
        old_route = self._items[index]
        self._attach(value)
        self._items[index] = value
        self._detach_if_removed(old_route)
        self._notify()

    def __delitem__(self, index: int | slice) -> None:
        removed = self._items[index] if isinstance(index, slice) else [self._items[index]]
        del self._items[index]
        for route in removed:
            self._detach_if_removed(route)
        self._notify()

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[RouteEdge]:
        return iter(self._items)

    def __repr__(self) -> str:
        return repr(self._items)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RouteCollection):
            return self._items == other._items
        if isinstance(other, list):
            return self._items == other
        return NotImplemented

    def __iadd__(self, other: Iterable[RouteEdge]) -> "RouteCollection":
        self.extend(other)
        return self

    def __imul__(self, value: int) -> "RouteCollection":
        raise TypeError("route graph collections do not support repetition")

    def append(self, value: RouteEdge) -> None:
        value = self._validate_route(value)
        self._attach(value)
        self._items.append(value)
        self._notify()

    def extend(self, iterable: Iterable[RouteEdge]) -> None:
        new_routes = [self._validate_route(route) for route in iterable]
        if not new_routes:
            return
        for route in new_routes:
            self._attach(route)
        self._items.extend(new_routes)
        self._notify()

    def insert(self, index: int, value: RouteEdge) -> None:
        value = self._validate_route(value)
        self._attach(value)
        self._items.insert(index, value)
        self._notify()

    def pop(self, index: int = -1) -> RouteEdge:
        value = self._items.pop(index)
        self._detach_if_removed(value)
        self._notify()
        return value

    def clear(self) -> None:
        if not self._items:
            return
        old_routes = list(self._items)
        self._items.clear()
        for route in old_routes:
            route._on_change = None
        self._notify()

    def reverse(self) -> None:
        self._items.reverse()
        self._notify()

    def sort(self, *, key=None, reverse: bool = False) -> None:
        self._items.sort(key=key, reverse=reverse)
        self._notify()


ObservableRouteList = RouteCollection


def replace_routes(
    current_routes: Iterable[RouteEdge],
    new_routes: Iterable[RouteEdge],
    *,
    on_change: Callable[[], None],
) -> RouteCollection:
    """Replace the active route collection and detach stale observers."""
    for route in current_routes:
        route._on_change = None
    return RouteCollection(new_routes, on_change=on_change)


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
