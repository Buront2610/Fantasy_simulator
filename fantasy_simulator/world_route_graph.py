"""Route graph helpers for ``World``.

This module isolates route observer wiring and adjacency indexing from the
aggregate so ``World`` can delegate cache maintenance.
"""

from __future__ import annotations

from collections.abc import Iterable as IterableABC
from collections.abc import Iterator, MutableSequence
from typing import Callable, Dict, Iterable, List, Mapping, overload

from .terrain import RouteEdge, Site


def _same_observer(left: Callable[[], None] | None, right: Callable[[], None] | None) -> bool:
    if left is right:
        return True
    if left is None or right is None:
        return False
    left_self = getattr(left, "__self__", None)
    right_self = getattr(right, "__self__", None)
    left_func = getattr(left, "__func__", None)
    right_func = getattr(right, "__func__", None)
    return left_self is right_self and left_func is right_func and left_func is not None


class RouteCollection(MutableSequence[RouteEdge]):
    """Route collection that invalidates cached adjacency on mutation."""

    def __init__(
        self,
        routes: Iterable[RouteEdge] = (),
        *,
        on_change: Callable[[], None] | None = None,
        owner_token: object | None = None,
        takeover_owner_token: object | None = None,
    ) -> None:
        self._items: list[RouteEdge] = []
        self._on_change = on_change
        self._owner_token = owner_token if owner_token is not None else object()
        self._takeover_owner_token = takeover_owner_token
        new_routes = [self._validate_route(route) for route in routes]
        self._ensure_unique_topology(new_routes)
        self._ensure_attachable(new_routes)
        for route in new_routes:
            self._attach(route)
        self._items = new_routes
        self._takeover_owner_token = None

    def _notify(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def _attach(self, route: RouteEdge) -> None:
        if not self._can_attach(route):
            raise ValueError("RouteEdge instances cannot be shared across active RouteCollection owners")
        route._on_change = self._on_change
        route._route_owner_token = self._owner_token

    def _can_attach(self, route: RouteEdge) -> bool:
        current_callback = route._on_change
        current_owner = getattr(route, "_route_owner_token", None)
        return (
            current_callback is None
            or current_owner is self._owner_token
            or current_owner is self._takeover_owner_token
            or (current_owner is None and _same_observer(current_callback, self._on_change))
        )

    def _ensure_attachable(self, routes: Iterable[RouteEdge]) -> None:
        if any(not self._can_attach(route) for route in routes):
            raise ValueError("RouteEdge instances cannot be shared across active RouteCollection owners")

    @staticmethod
    def _route_pair(route: RouteEdge) -> tuple[str, str]:
        first_site_id, second_site_id = sorted((route.from_site_id, route.to_site_id))
        return first_site_id, second_site_id

    @classmethod
    def _ensure_unique_topology(cls, routes: Iterable[RouteEdge]) -> None:
        validate_route_topology(routes)

    @staticmethod
    def _validate_route(route: object) -> RouteEdge:
        if not isinstance(route, RouteEdge):
            raise TypeError("route collection entries must be RouteEdge instances")
        if route.from_site_id == route.to_site_id:
            raise ValueError(f"route collection cannot contain self-loop route: {route.route_id!r}")
        return route

    def _contains_identity(self, route: RouteEdge) -> bool:
        return any(item is route for item in self._items)

    def _detach_if_removed(self, route: RouteEdge) -> None:
        if not self._contains_identity(route) and getattr(route, "_route_owner_token", None) is self._owner_token:
            route._on_change = None
            route._route_owner_token = None

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
            if index.step not in (None, 1) and len(old_routes) != len(new_routes):
                raise ValueError(
                    f"attempt to assign sequence of size {len(new_routes)} "
                    f"to extended slice of size {len(old_routes)}"
                )
            new_items = list(self._items)
            new_items[index] = new_routes
            self._ensure_unique_topology(new_items)
            self._ensure_attachable(new_routes)
            for route in new_routes:
                self._attach(route)
            self._items = new_items
            for route in old_routes:
                self._detach_if_removed(route)
            self._notify()
            return
        value = self._validate_route(value)
        old_route = self._items[index]
        new_items = list(self._items)
        new_items[index] = value
        self._ensure_unique_topology(new_items)
        self._ensure_attachable([value])
        self._attach(value)
        self._items = new_items
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
        new_items = list(self._items)
        new_items.append(value)
        self._ensure_unique_topology(new_items)
        self._ensure_attachable([value])
        self._attach(value)
        self._items = new_items
        self._notify()

    def extend(self, iterable: Iterable[RouteEdge]) -> None:
        new_routes = [self._validate_route(route) for route in iterable]
        if not new_routes:
            return
        new_items = list(self._items)
        new_items.extend(new_routes)
        self._ensure_unique_topology(new_items)
        self._ensure_attachable(new_routes)
        for route in new_routes:
            self._attach(route)
        self._items = new_items
        self._notify()

    def insert(self, index: int, value: RouteEdge) -> None:
        value = self._validate_route(value)
        new_items = list(self._items)
        new_items.insert(index, value)
        self._ensure_unique_topology(new_items)
        self._ensure_attachable([value])
        self._attach(value)
        self._items = new_items
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
            if getattr(route, "_route_owner_token", None) is self._owner_token:
                route._on_change = None
                route._route_owner_token = None
        self._notify()

    def reverse(self) -> None:
        self._items.reverse()
        self._notify()

    def sort(self, *, key=None, reverse: bool = False) -> None:
        self._items.sort(key=key, reverse=reverse)
        self._notify()


ObservableRouteList = RouteCollection


def route_pair(route: RouteEdge) -> tuple[str, str]:
    """Return the undirected endpoint pair used for route topology checks."""
    first_site_id, second_site_id = sorted((route.from_site_id, route.to_site_id))
    return first_site_id, second_site_id


def validate_route_topology(routes: Iterable[RouteEdge]) -> None:
    """Reject route identity shapes that would make adjacency ambiguous."""
    seen_route_ids: set[str] = set()
    seen_route_pairs: set[tuple[str, str]] = set()
    for route in routes:
        if route.from_site_id == route.to_site_id:
            raise ValueError(f"route collection contains self-loop: {route.route_id!r}")
        if route.route_id in seen_route_ids:
            raise ValueError(f"route collection contains duplicate route id: {route.route_id!r}")
        seen_route_ids.add(route.route_id)
        current_route_pair = route_pair(route)
        if current_route_pair in seen_route_pairs:
            raise ValueError(
                f"route collection contains duplicate route pair: {current_route_pair[0]}->{current_route_pair[1]}"
            )
        seen_route_pairs.add(current_route_pair)


def replace_routes(
    current_routes: Iterable[RouteEdge],
    new_routes: Iterable[RouteEdge],
    *,
    on_change: Callable[[], None],
    owner_token: object | None = None,
) -> RouteCollection:
    """Replace the active route collection and detach stale observers."""
    old_routes = list(current_routes)
    current_owner = getattr(current_routes, "_owner_token", None)
    resolved_owner_token = owner_token if owner_token is not None else object()
    new_collection = RouteCollection(
        new_routes,
        on_change=on_change,
        owner_token=resolved_owner_token,
        takeover_owner_token=current_owner,
    )
    new_route_ids = {id(route) for route in new_collection}
    for route in old_routes:
        if id(route) not in new_route_ids and getattr(route, "_route_owner_token", None) is current_owner:
            route._on_change = None
            route._route_owner_token = None
    return new_collection


def attach_route_observers(
    routes: Iterable[RouteEdge],
    *,
    on_change: Callable[[], None],
    owner_token: object | None = None,
) -> None:
    """Attach mutation hooks to each route in the active collection."""
    route_owner = getattr(routes, "_owner_token", owner_token)
    for route in routes:
        current_callback = route._on_change
        if current_callback is None:
            route._on_change = on_change
            route._route_owner_token = route_owner
            continue
        current_owner = getattr(route, "_route_owner_token", None)
        if current_owner is not route_owner and not (
            current_owner is None and _same_observer(current_callback, on_change)
        ):
            raise ValueError("RouteEdge instances cannot be shared across active RouteCollection owners")
        route._route_owner_token = route_owner


def rebuild_route_index(
    *,
    sites: Iterable[Site],
    routes: Iterable[RouteEdge],
    on_change: Callable[[], None],
    owner_token: object | None = None,
) -> Dict[str, List[RouteEdge]]:
    """Build route adjacency lists keyed by endpoint location ID."""
    site_list = list(sites)
    route_list = list(routes)
    validate_route_topology(route_list)
    route_owner = getattr(routes, "_owner_token", owner_token)
    attach_route_observers(route_list, on_change=on_change, owner_token=route_owner)
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
