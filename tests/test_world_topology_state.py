from __future__ import annotations

import pytest

from fantasy_simulator.content.setting_bundle import (
    NamingRulesDefinition,
    SettingBundle,
    SiteSeedDefinition,
    WorldDefinition,
)
from fantasy_simulator.terrain import RouteEdge
from fantasy_simulator.world import World
from fantasy_simulator.world_topology_state import (
    overlay_serialized_route_state,
    restore_serialized_topology,
)


def test_restore_serialized_topology_normalizes_location_ids_before_validation() -> None:
    world = World(name="Custom")
    world.setting_bundle = SettingBundle(
        schema_version=1,
        world_definition=WorldDefinition(
            world_key="custom",
            display_name="Custom",
            lore_text="Custom lore",
            site_seeds=[
                SiteSeedDefinition(
                    location_id="hub_primary",
                    name="Clockwork Hub",
                    description="Primary site.",
                    region_type="city",
                    x=0,
                    y=0,
                ),
            ],
            naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
        ),
    )

    topology = restore_serialized_topology(
        terrain_map_data={
            "width": 1,
            "height": 1,
            "cells": [{"x": 0, "y": 0, "biome": "plains", "elevation": 128, "moisture": 128, "temperature": 128}],
        },
        site_data=[
            {
                "location_id": "loc_clockwork_hub",
                "x": 0,
                "y": 0,
                "site_type": "city",
                "importance": 50,
            }
        ],
        route_data=[],
        normalize_location_id=world.normalize_location_id,
        location_index=world._location_id_index,
    )

    assert topology.route_graph_explicit is True
    assert topology.sites[0].location_id == "hub_primary"


def test_overlay_serialized_route_state_rejects_endpoint_mismatch() -> None:
    routes = [RouteEdge("route_1", "loc_one", "loc_two", "road", 3, blocked=False)]

    with pytest.raises(ValueError, match="disagrees with canonical endpoints"):
        overlay_serialized_route_state(
            routes,
            [
                {
                    "route_id": "route_1",
                    "from_site_id": "loc_one",
                    "to_site_id": "loc_three",
                    "route_type": "road",
                    "distance": 3,
                    "blocked": False,
                }
            ],
        )
