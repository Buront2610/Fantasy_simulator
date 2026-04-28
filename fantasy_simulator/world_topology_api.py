"""Topology methods for :class:`fantasy_simulator.world.World`."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .terrain import AtlasLayout, RouteEdge, Site
from .world_route_graph import routes_for_site
from .world_topology import PROPAGATION_TOPOLOGY_TRAVEL
from .world_topology_queries import (
    connected_site_ids,
    grid_neighboring_locations,
    propagation_neighboring_locations,
    reachable_location_ids as reachable_topology_location_ids,
    travel_neighboring_locations,
)
from .world_topology_runtime import apply_topology_state, route_index_by_site, site_index_by_location
from .world_topology_state import (
    WorldTopologyState,
    build_atlas_layout_from_topology,
    build_topology_from_locations,
    overlay_serialized_route_state,
    validate_topology_integrity,
)


class WorldTopologyMixin:
    def _build_terrain_from_grid(self, *, explicit_route_graph: Optional[bool] = None) -> None:
        """Generate terrain, sites, and routes from the current grid."""
        use_explicit_route_graph = (
            self._grid_matches_bundle_seeds()
            if explicit_route_graph is None
            else explicit_route_graph
        )
        location_ids = set(self._location_id_index)
        topology_state = build_topology_from_locations(
            width=self.width,
            height=self.height,
            locations=self.grid.values(),
            route_specs=(
                [
                    seed.to_dict()
                    for seed in self._setting_bundle.world_definition.route_seeds
                    if seed.from_site_id in location_ids and seed.to_site_id in location_ids
                ]
                if use_explicit_route_graph
                else None
            ),
            explicit_route_graph=use_explicit_route_graph,
        )
        self._apply_topology_state(topology_state)

    def _apply_topology_state(self, topology_state: WorldTopologyState) -> None:
        """Apply a reconstructed topology snapshot to the live world state."""
        apply_topology_state(self, topology_state)

    def _build_atlas_layout_from_current_state(self) -> AtlasLayout:
        """Generate the persistent atlas layout from current terrain/site data."""
        return build_atlas_layout_from_topology(
            width=self.width,
            height=self.height,
            terrain_map=self.terrain_map,
            sites=self.sites,
            routes=self.routes,
        )

    def _rebuild_site_index(self) -> None:
        """Rebuild the site lookup index keyed by location_id."""
        self._site_index = site_index_by_location(self.sites)

    def _mark_routes_dirty(self) -> None:
        """Mark cached route adjacency as stale after route mutations."""
        self._routes_dirty = True

    def _rebuild_route_index(self) -> None:
        """Rebuild route adjacency lists keyed by endpoint location id."""
        self._routes_by_site = route_index_by_site(
            sites=self.sites,
            routes=self.routes,
            on_change=self._mark_routes_dirty,
        )
        self._routes_dirty = False

    def _ensure_route_index_current(self) -> None:
        """Keep the cached route adjacency in sync with direct route reassignment."""
        if self._routes_dirty:
            self._rebuild_route_index()

    def _validate_topology_integrity(self) -> None:
        """Validate that restored topology is coherent with the active grid."""
        validate_topology_integrity(
            sites=self.sites,
            routes=self.routes,
            location_index=self._location_id_index,
        )

    def get_site_by_id(self, location_id: str) -> Optional[Site]:
        """Return the Site record for a location, or None."""
        return self._site_index.get(location_id)

    def get_routes_for_site(self, location_id: str) -> List[RouteEdge]:
        """Return all routes connected to a site."""
        self._ensure_route_index_current()
        return routes_for_site(self._routes_by_site, location_id)

    def get_connected_site_ids(self, location_id: str) -> List[str]:
        """Return location_ids of sites reachable via routes from a site."""
        return connected_site_ids(
            location_id,
            get_routes_for_site=self.get_routes_for_site,
        )

    def get_grid_neighboring_locations(self, location_id: str) -> List[Any]:
        """Return adjacency by physical map grid, regardless of route state."""
        return grid_neighboring_locations(
            location_id,
            location_index=self._location_id_index,
            grid=self.grid,
        )

    def get_travel_neighboring_locations(self, location_id: str) -> List[Any]:
        """Return neighbors reachable for travel using the travel topology contract."""
        return travel_neighboring_locations(
            location_id,
            location_index=self._location_id_index,
            grid=self.grid,
            routes=self.routes,
            route_graph_explicit=self._route_graph_explicit,
            get_routes_for_site=self.get_routes_for_site,
        )

    def get_propagation_neighboring_locations(
        self,
        location_id: str,
        *,
        mode: str | None = None,
        include_blocked_routes: bool | None = None,
    ) -> List[Any]:
        """Return neighbors used for state propagation."""
        topology_rules = self.propagation_rules.get("topology", {})
        topology_mode = mode or str(topology_rules.get("mode", PROPAGATION_TOPOLOGY_TRAVEL))
        effective_include_blocked_routes = (
            bool(topology_rules.get("include_blocked_routes", False))
            if include_blocked_routes is None
            else include_blocked_routes
        )
        return propagation_neighboring_locations(
            location_id,
            location_index=self._location_id_index,
            grid=self.grid,
            routes=self.routes,
            route_graph_explicit=self._route_graph_explicit,
            get_routes_for_site=self.get_routes_for_site,
            topology_mode=topology_mode,
            include_blocked_routes=effective_include_blocked_routes,
        )

    def reachable_location_ids(self, location_id: str) -> List[str]:
        """Return all reachable location_ids from ``location_id``."""
        return reachable_topology_location_ids(
            location_id,
            location_index=self._location_id_index,
            get_travel_neighbors=self.get_travel_neighboring_locations,
        )

    def _overlay_serialized_route_state(self, serialized_routes: List[Dict[str, Any]]) -> None:
        """Overlay mutable route state onto the canonical route graph."""
        overlay_serialized_route_state(self.routes, serialized_routes)
