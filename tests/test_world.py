"""
tests/test_world.py - Unit tests for the World class.
"""

import unicodedata
import pytest

from fantasy_simulator.adventure import AdventureRun
from fantasy_simulator.character import Character
from fantasy_simulator.content.setting_bundle import (
    CalendarDefinition,
    CalendarMonthDefinition,
    NamingRulesDefinition,
    SettingBundle,
    SiteSeedDefinition,
    WorldDefinition,
)
from fantasy_simulator.i18n import set_locale
from fantasy_simulator.rumor import Rumor
from fantasy_simulator.terrain import RouteEdge
from fantasy_simulator.world import LocationState, MemorialRecord, World
from fantasy_simulator.content.world_data import get_location_state_defaults


def _make_char(name="Aldric", location_id="loc_aethoria_capital"):
    return Character(
        name=name, age=25, gender="Male", race="Human", job="Warrior", location_id=location_id,
    )


def _display_width(text: str) -> int:
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("F", "W") else 1
    return width


class TestWorld:
    def test_render_map_contains_header(self):
        set_locale("en")
        world = World()
        rendered = world.render_map()
        assert "WORLD MAP" in rendered
        assert "Aethoria" in rendered
        assert "Safety" in rendered
        assert "Danger" in rendered
        assert "Traffic" in rendered

    def test_render_map_uses_highlight_marker(self):
        world = World()
        rendered = world.render_map(highlight_location="loc_aethoria_capital")
        assert "*" in rendered

    def test_render_map_lines_have_stable_ascii_width_in_english(self):
        set_locale("en")
        world = World()
        lines = world.render_map().splitlines()
        lengths = {len(line) for line in lines}
        assert len(lengths) == 1

    def test_render_map_lines_have_stable_display_width_in_japanese(self):
        set_locale("ja")
        world = World()
        lines = world.render_map().splitlines()
        widths = {_display_width(line) for line in lines}
        assert len(widths) == 1

    def test_render_map_localizes_region_type_in_japanese(self):
        set_locale("ja")
        rendered = World().render_map()
        assert "地形: 都市" in rendered
        assert "地形: city" not in rendered

    def test_get_neighboring_locations_returns_adjacent_cells(self):
        world = World()
        neighbors = world.get_neighboring_locations("loc_aethoria_capital")
        assert neighbors
        assert all(hasattr(loc, "canonical_name") for loc in neighbors)

    def test_propagation_topology_can_diverge_from_travel_topology(self):
        world = World()
        route = world.routes[0]
        source = world.get_location_by_id(route.from_site_id)
        target = world.get_location_by_id(route.to_site_id)
        assert source is not None
        assert target is not None

        assert target in world.get_travel_neighboring_locations(source.id)
        route.blocked = True

        assert target not in world.get_travel_neighboring_locations(source.id)
        assert target in world.get_propagation_neighboring_locations(source.id, mode="grid")

        source.danger = 90
        target.danger = 0
        world.propagation_rules["topology"]["mode"] = "grid"
        world.propagate_state(months=12)

        assert target.danger > 0

    def test_route_index_rebuilds_after_in_place_route_replacement(self):
        world = World()
        target_index = next(
            idx for idx, route in enumerate(world.routes)
            if route.other_end("loc_aethoria_capital") == "loc_silverbrook"
        )
        world.routes[target_index] = RouteEdge(
            route_id="route_capital_coral",
            from_site_id="loc_aethoria_capital",
            to_site_id="loc_coral_cove",
            route_type="road",
        )

        neighbor_ids = set(world.get_connected_site_ids("loc_aethoria_capital"))

        assert "loc_coral_cove" in neighbor_ids
        assert "loc_silverbrook" not in neighbor_ids

    def test_route_cache_clean_reads_do_not_recompute_signatures(self, monkeypatch):
        world = World()
        rebuild_calls = 0
        original_rebuild = world._rebuild_route_index

        def _counting_rebuild():
            nonlocal rebuild_calls
            rebuild_calls += 1
            original_rebuild()

        monkeypatch.setattr(world, "_rebuild_route_index", _counting_rebuild)

        routes = world.get_routes_for_site("loc_aethoria_capital")

        assert routes
        assert rebuild_calls == 0

    def test_route_block_toggle_invalidates_cache_without_signature_scan(self, monkeypatch):
        world = World()
        route = next(
            route for route in world.routes
            if route.other_end("loc_aethoria_capital") == "loc_silverbrook"
        )
        rebuild_calls = 0
        original_rebuild = world._rebuild_route_index

        def _counting_rebuild():
            nonlocal rebuild_calls
            rebuild_calls += 1
            original_rebuild()

        monkeypatch.setattr(world, "_rebuild_route_index", _counting_rebuild)

        assert "loc_silverbrook" in world.get_connected_site_ids("loc_aethoria_capital")
        route.blocked = True

        assert "loc_silverbrook" not in world.get_connected_site_ids("loc_aethoria_capital")
        assert rebuild_calls == 1

    def test_setting_bundle_can_define_explicitly_disconnected_topology(self):
        world = World(name="Disconnected", width=2, height=1)
        world.setting_bundle = SettingBundle(
            schema_version=1,
            world_definition=WorldDefinition(
                world_key="disconnected",
                display_name="Disconnected",
                lore_text="No roads",
                site_seeds=[
                    SiteSeedDefinition(
                        location_id="loc_one",
                        name="One",
                        description="",
                        region_type="city",
                        x=0,
                        y=0,
                    ),
                    SiteSeedDefinition(
                        location_id="loc_two",
                        name="Two",
                        description="",
                        region_type="village",
                        x=1,
                        y=0,
                    ),
                ],
                route_seeds=[],
            ),
        )

        assert world.routes == []
        assert world.get_connected_site_ids("loc_one") == []
        assert world.get_travel_neighboring_locations("loc_one") == []
        assert world.get_neighboring_locations("loc_one") == []
        assert world.reachable_location_ids("loc_one") == []
        assert world.get_propagation_neighboring_locations("loc_one", mode="travel") == []

    def test_add_character_marks_location_visited(self):
        world = World()
        capital = world.get_location_by_id("loc_aethoria_capital")
        assert capital is not None
        assert capital.visited is False
        world.add_character(_make_char())
        assert capital.visited is True

    def test_add_character_with_blank_location_uses_default_resident(self):
        world = World()
        character = Character("Wanderer", 25, "Male", "Human", "Warrior", location_id="")

        world.add_character(character)

        assert character.location_id == world._default_resident_location_id()

    def test_locations_have_state_defaults(self):
        world = World()
        capital = world.get_location_by_id("loc_aethoria_capital")
        assert capital is not None
        assert capital.canonical_name == "Aethoria Capital"
        assert capital.prosperity == 85
        assert capital.safety == 80
        assert capital.danger == 15

    def test_custom_bundle_capital_tag_drives_default_state_profile(self):
        world = World(name="Custom")
        world.setting_bundle = SettingBundle(
            schema_version=1,
            world_definition=WorldDefinition(
                world_key="custom",
                display_name="Custom",
                lore_text="Custom lore",
                site_seeds=[
                    SiteSeedDefinition(
                        location_id="loc_custom_capital",
                        name="Custom Capital",
                        description="The tagged capital.",
                        region_type="city",
                        x=0,
                        y=0,
                        tags=["capital", "default_resident"],
                    ),
                ],
                naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
            ),
        )

        capital = world.get_location_by_id("loc_custom_capital")

        assert capital is not None
        assert capital.safety == 80
        assert capital.danger == 15
        assert world._default_resident_location_id() == "loc_custom_capital"

        capital.safety = 70
        world._decay_toward_baseline()
        assert capital.safety > 70

        restored = World.from_dict(world.to_dict())
        restored_capital = restored.get_location_by_id("loc_custom_capital")
        assert restored_capital is not None
        assert restored.location_state_defaults("loc_custom_capital", "city")["safety"] == 80

    def test_from_dict_recovers_missing_location_id_from_active_bundle_site_seeds(self):
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
                        description="A custom site with a non-slug ID.",
                        region_type="city",
                        x=0,
                        y=0,
                    ),
                ],
                naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
            ),
        )
        payload = world.to_dict()
        payload["grid"][0].pop("id")

        restored = World.from_dict(payload)

        location = restored.get_location_by_id("hub_primary")
        assert location is not None
        assert location.canonical_name == "Clockwork Hub"

    def test_from_dict_prefers_bundle_name_mapping_when_stored_id_is_stale(self):
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
                        description="A custom site with a non-slug ID.",
                        region_type="city",
                        x=0,
                        y=0,
                    ),
                ],
                naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
            ),
        )
        payload = world.to_dict()
        payload["grid"][0]["id"] = "stale_id"

        restored = World.from_dict(payload)

        location = restored.get_location_by_id("hub_primary")
        assert location is not None
        assert restored.get_location_by_id("stale_id") is None

    def test_normalize_location_id_keeps_recognized_current_id_even_if_name_differs(self):
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
                    SiteSeedDefinition(
                        location_id="hub_secondary",
                        name="Second Hub",
                        description="Secondary site.",
                        region_type="city",
                        x=1,
                        y=0,
                    ),
                ],
                naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
            ),
        )
        assert world.normalize_location_id("hub_secondary", location_name="Clockwork Hub") == "hub_secondary"

    def test_setting_bundle_assignment_rebuilds_world_structure(self):
        world = World(name="Custom")
        old_location_ids = set(world.location_ids)
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
                        description="A custom site.",
                        region_type="city",
                        x=0,
                        y=0,
                    ),
                ],
                naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
            ),
        )

        assert world.location_ids == ["hub_primary"]
        assert old_location_ids.isdisjoint(world.location_ids)
        assert world.get_site_by_id("hub_primary") is not None
        assert world.atlas_layout is not None

    def test_setting_bundle_assignment_preserves_runtime_state_for_matching_location_ids(self):
        world = World()
        capital = world.get_location_by_id("loc_aethoria_capital")
        assert capital is not None
        capital.danger = 42
        capital.visited = True

        world.setting_bundle = SettingBundle.from_dict(world.setting_bundle.to_dict())

        rebuilt = world.get_location_by_id("loc_aethoria_capital")
        assert rebuilt is not None
        assert rebuilt.danger == 42
        assert rebuilt.visited is True

    def test_setting_bundle_assignment_deep_copies_live_traces(self):
        world = World()
        capital = world.get_location_by_id("loc_aethoria_capital")
        assert capital is not None
        capital.live_traces.append({"kind": "omen", "value": 1})

        world.setting_bundle = SettingBundle.from_dict(world.setting_bundle.to_dict())
        rebuilt = world.get_location_by_id("loc_aethoria_capital")
        assert rebuilt is not None

        capital.live_traces[0]["value"] = 99

        assert rebuilt.live_traces[0]["value"] == 1

    def test_setting_bundle_getter_returns_snapshot_not_live_mutable_reference(self):
        world = World()

        bundle = world.setting_bundle
        bundle.world_definition.display_name = "Mutated Elsewhere"

        assert world.name == "Aethoria"

    def test_setting_bundle_assignment_clones_source_bundle(self):
        world = World()
        bundle = world.setting_bundle

        world.setting_bundle = bundle
        bundle.world_definition.display_name = "Mutated Source Bundle"

        assert world.name == "Aethoria"

    def test_setting_bundle_assignment_does_not_alias_across_worlds(self):
        shared_bundle = SettingBundle(
            schema_version=1,
            world_definition=WorldDefinition(
                world_key="shared",
                display_name="Shared",
                lore_text="Shared lore",
                site_seeds=[
                    SiteSeedDefinition(
                        location_id="shared_hub",
                        name="Shared Hub",
                        description="A shared site.",
                        region_type="city",
                        x=0,
                        y=0,
                    ),
                ],
                naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
            ),
        )
        first = World(name="First")
        second = World(name="Second")

        first.setting_bundle = shared_bundle
        second.setting_bundle = shared_bundle
        shared_bundle.world_definition.display_name = "Mutated Shared"

        assert first.name == "Shared"
        assert second.name == "Shared"

    def test_setting_bundle_assignment_with_no_sites_clears_invalid_character_locations(self):
        world = World()
        world.add_character(_make_char())

        world.setting_bundle = SettingBundle(
            schema_version=1,
            world_definition=WorldDefinition(
                world_key="empty",
                display_name="Empty",
                lore_text="No sites here.",
                site_seeds=[],
                naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
            ),
        )

        assert world.characters[0].location_id == ""
        assert world.location_ids == []

    def test_setting_bundle_assignment_repairs_rumor_adventure_and_memorial_locations(self):
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
                    SiteSeedDefinition(
                        location_id="hub_secondary",
                        name="Second Hub",
                        description="Secondary site.",
                        region_type="city",
                        x=1,
                        y=0,
                    ),
                ],
                naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
            ),
        )
        world.rumors.append(Rumor(source_location_id="hub_secondary", description="Old rumor"))
        world.active_adventures.append(
            AdventureRun(
                character_id="char_1",
                character_name="Aldric",
                origin="hub_secondary",
                destination="hub_secondary",
                year_started=world.year,
            )
        )
        world.memorials["mem_1"] = MemorialRecord(
            memorial_id="mem_1",
            character_id="char_1",
            character_name="Aldric",
            location_id="hub_secondary",
            year=world.year,
            cause="battle_fatal",
            epitaph="Fell in battle.",
        )

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

        assert world.rumors[0].source_location_id is None
        assert world.active_adventures[0].origin == "hub_primary"
        assert world.active_adventures[0].destination == "hub_primary"
        assert world.memorials["mem_1"].location_id == "hub_primary"
        assert world.get_location_by_id("hub_primary").memorial_ids == ["mem_1"]

    def test_random_location_raises_clear_error_for_empty_world(self):
        world = World()
        world.setting_bundle = SettingBundle(
            schema_version=1,
            world_definition=WorldDefinition(
                world_key="empty",
                display_name="Empty",
                lore_text="No sites here.",
                site_seeds=[],
                naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
            ),
        )

        try:
            world.random_location()
        except ValueError as exc:
            assert "World has no locations." in str(exc)
        else:
            raise AssertionError("Expected ValueError for empty-world random_location")

    def test_build_default_map_rebuilds_instead_of_appending(self):
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
                        description="A custom site.",
                        region_type="city",
                        x=0,
                        y=0,
                    ),
                ],
                naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
            ),
        )
        world._register_location(
            LocationState(
                id="loc_stale",
                canonical_name="Stale",
                description="Should disappear.",
                region_type="city",
                x=1,
                y=1,
                **get_location_state_defaults("loc_stale", "city"),
            )
        )

        world._build_default_map()

        assert world.location_ids == ["hub_primary"]

    def test_default_world_uses_bundle_site_seeds(self):
        world = World(width=2, height=1)

        expected_entries = [
            seed.as_world_data_entry()
            for seed in world.setting_bundle.world_definition.site_seeds
            if seed.x < 2 and seed.y < 1
        ]

        assert world.default_location_entries() == expected_entries
        assert sorted((loc.id, loc.x, loc.y) for loc in world.grid.values()) == sorted(
            (loc_id, x, y) for loc_id, _name, _desc, _rtype, x, y in expected_entries
        )

    def test_location_state_constructor_sets_fields(self):
        defaults = get_location_state_defaults("loc_custom_city", "city")
        location = LocationState(
            id="loc_custom_city",
            canonical_name="Custom City",
            description="A custom settlement.",
            region_type="city",
            x=1,
            y=1,
            **defaults,
        )
        assert location.canonical_name == "Custom City"
        assert location.name == "Custom City"
        assert location.prosperity == 70

    def test_location_labels_derive_from_state(self):
        set_locale("en")
        world = World()
        thornwood = world.get_location_by_id("loc_thornwood")
        assert thornwood is not None
        assert thornwood.safety_label == "dangerous"
        assert thornwood.mood_label == "anxious"

    def test_to_dict_round_trip_preserves_adventure_lists(self):
        world = World()
        char = _make_char()
        world.add_character(char)
        payload = world.to_dict()
        restored = World.from_dict(payload)
        assert restored.name == world.name
        assert restored.year == world.year
        assert restored.active_adventures == []
        assert restored.completed_adventures == []

    def test_name_is_bundle_backed_source_of_truth(self):
        world = World(name="Aethoria")

        world.name = "Renamed Realm"

        assert world.setting_bundle.world_definition.display_name == "Renamed Realm"
        restored = World.from_dict(world.to_dict())
        assert restored.name == "Renamed Realm"
        assert restored.setting_bundle.world_definition.display_name == "Renamed Realm"

    def test_lore_is_bundle_backed_source_of_truth(self):
        world = World()

        world.lore = "Custom lore"

        assert world.setting_bundle.world_definition.lore_text == "Custom lore"
        payload = world.to_dict()
        assert payload["lore"] == "Custom lore"
        restored = World.from_dict(payload)
        assert restored.lore == "Custom lore"
        assert restored.setting_bundle.world_definition.lore_text == "Custom lore"

    def test_from_dict_rebuilds_bundle_backed_world_structure_when_grid_is_missing_entries(self):
        world = World(width=2, height=1)
        payload = world.to_dict()
        payload["grid"] = []

        restored = World.from_dict(payload)

        assert restored.default_location_entries() == world.default_location_entries()
        assert restored.location_ids == world.location_ids

    def test_from_dict_uses_bundle_structure_and_overlays_runtime_state(self):
        world = World(width=2, height=1)
        location = next(iter(world.grid.values()))
        location.danger = 42
        location.visited = True
        payload = world.to_dict()
        next(loc for loc in payload["grid"] if loc["id"] == location.id)["id"] = "stale_id"

        restored = World.from_dict(payload)

        restored_location = restored.get_location_by_id(location.id)
        assert restored_location is not None
        assert restored_location.danger == 42
        assert restored_location.visited is True
        assert restored.get_location_by_id("stale_id") is None

    def test_from_dict_rejects_embedded_bundle_with_duplicate_site_ids(self):
        payload = World().to_dict()
        payload["setting_bundle"]["world_definition"]["site_seeds"] = [
            {
                "location_id": "loc_dup",
                "name": "One",
                "description": "",
                "region_type": "city",
                "x": 0,
                "y": 0,
            },
            {
                "location_id": "loc_dup",
                "name": "Two",
                "description": "",
                "region_type": "city",
                "x": 1,
                "y": 0,
            },
        ]

        try:
            World.from_dict(payload)
        except ValueError as exc:
            assert "duplicate site seed ids" in str(exc)
        else:
            raise AssertionError("Expected ValueError for invalid embedded setting_bundle")

    def test_from_dict_rejects_embedded_bundle_with_incomplete_naming_rules(self):
        payload = World().to_dict()
        payload["setting_bundle"]["world_definition"]["naming_rules"] = {
            "first_names_non_binary": ["Quill"],
            "last_names": ["Ink"],
        }

        try:
            World.from_dict(payload)
        except ValueError as exc:
            assert "first_names_male" in str(exc)
        else:
            raise AssertionError("Expected ValueError for invalid embedded naming rules")

    def test_get_characters_at_location_only_returns_alive(self):
        world = World()
        alive = _make_char("Alive")
        dead = _make_char("Dead")
        dead.alive = False
        world.add_character(alive)
        world.add_character(dead)
        chars = world.get_characters_at_location("loc_aethoria_capital")
        assert [c.name for c in chars] == ["Alive"]

    def test_random_location_uses_injected_rng(self):
        world = World()

        class FixedRng:
            def choice(self, options):
                return options[-1]

        location = world.random_location(rng=FixedRng())
        assert location == list(world.grid.values())[-1]

    def test_log_event_uses_localized_year_prefix_english(self):
        set_locale("en")
        world = World(year=1042)
        world.log_event("Something happened.")
        assert world.event_log[-1] == "[Year 1042] Something happened."

    def test_log_event_uses_localized_year_prefix_japanese(self):
        set_locale("ja")
        world = World(year=1042)
        world.log_event("何かが起きた。")
        entry = world.event_log[-1]
        assert "[1042年]" in entry
        assert "何かが起きた。" in entry
        assert "[Year" not in entry
        set_locale("en")

    def test_record_event_stores_structured_record(self):
        from fantasy_simulator.events import WorldEventRecord
        world = World()
        record = WorldEventRecord(kind="battle", year=1001, location_id="loc_aethoria_capital")
        world.record_event(record)
        assert len(world.event_records) == 1
        assert world.event_records[0].kind == "battle"

    def test_get_events_by_location(self):
        from fantasy_simulator.events import WorldEventRecord
        world = World()
        world.record_event(WorldEventRecord(kind="battle", year=1001, location_id="loc_thornwood"))
        world.record_event(WorldEventRecord(kind="meeting", year=1001, location_id="loc_aethoria_capital"))
        world.record_event(WorldEventRecord(kind="discovery", year=1002, location_id="loc_thornwood"))
        results = world.get_events_by_location("loc_thornwood")
        assert len(results) == 2
        assert all(r.location_id == "loc_thornwood" for r in results)

    def test_get_events_by_actor(self):
        from fantasy_simulator.events import WorldEventRecord
        world = World()
        world.record_event(WorldEventRecord(
            kind="battle", year=1001, primary_actor_id="a1", secondary_actor_ids=["a2"],
        ))
        world.record_event(WorldEventRecord(kind="journey", year=1001, primary_actor_id="a3"))
        assert len(world.get_events_by_actor("a1")) == 1
        assert len(world.get_events_by_actor("a2")) == 1
        assert len(world.get_events_by_actor("a3")) == 1
        assert len(world.get_events_by_actor("unknown")) == 0

    def test_get_events_by_year(self):
        from fantasy_simulator.events import WorldEventRecord
        world = World()
        world.record_event(WorldEventRecord(kind="battle", year=1001))
        world.record_event(WorldEventRecord(kind="meeting", year=1002))
        world.record_event(WorldEventRecord(kind="journey", year=1001))
        assert len(world.get_events_by_year(1001)) == 2
        assert len(world.get_events_by_year(1002)) == 1

    def test_event_records_in_to_dict_round_trip(self):
        from fantasy_simulator.events import WorldEventRecord
        world = World()
        world.record_event(WorldEventRecord(kind="battle", year=1001, location_id="loc_thornwood"))
        payload = world.to_dict()
        restored = World.from_dict(payload)
        assert len(restored.event_records) == 1
        assert restored.event_records[0].kind == "battle"
        assert restored.event_records[0].location_id == "loc_thornwood"

    def test_world_round_trip_preserves_location_state(self):
        world = World()
        capital = world.get_location_by_id("loc_aethoria_capital")
        assert capital is not None
        capital.danger = 42
        capital.visited = True
        restored = World.from_dict(world.to_dict())
        restored_capital = restored.get_location_by_id("loc_aethoria_capital")
        assert restored_capital is not None
        assert restored_capital.danger == 42
        assert restored_capital.visited is True

    def test_world_to_dict_deep_copies_live_traces(self):
        world = World()
        capital = world.get_location_by_id("loc_aethoria_capital")
        assert capital is not None
        capital.live_traces.append({"kind": "omen", "value": 1})

        payload = world.to_dict()
        capital_payload = next(loc for loc in payload["grid"] if loc["id"] == "loc_aethoria_capital")
        capital_payload["live_traces"][0]["value"] = 99

        assert capital.live_traces[0]["value"] == 1

    def test_world_from_dict_deep_copies_live_traces(self):
        world = World()
        capital = world.get_location_by_id("loc_aethoria_capital")
        assert capital is not None
        capital.live_traces.append({"kind": "omen", "value": 1})
        payload = world.to_dict()

        restored = World.from_dict(payload)
        capital_payload = next(loc for loc in payload["grid"] if loc["id"] == "loc_aethoria_capital")
        capital_payload["live_traces"][0]["value"] = 99

        restored_capital = restored.get_location_by_id("loc_aethoria_capital")
        assert restored_capital is not None
        assert restored_capital.live_traces[0]["value"] == 1

    def test_custom_calendar_round_trips_with_world(self):
        world = World()
        custom_bundle = SettingBundle(
            schema_version=1,
            world_definition=WorldDefinition(
                world_key="custom",
                display_name="Custom World",
                lore_text="Custom lore",
                calendar=CalendarDefinition(
                    calendar_key="lunar_cycle",
                    display_name="Lunar Cycle",
                    months=[
                        CalendarMonthDefinition("wax", "Wax", 20, season="winter"),
                        CalendarMonthDefinition("wane", "Wane", 35, season="summer"),
                    ],
                ),
            ),
        )
        world.setting_bundle = custom_bundle

        restored = World.from_dict(world.to_dict())

        assert world.calendar_baseline.calendar_key == "lunar_cycle"
        assert restored.months_per_year == 2
        assert restored.days_in_month(1) == 20
        assert restored.days_in_month(2) == 35
        assert restored.season_for_month(2) == "summer"
        assert restored.calendar_baseline.calendar_key == "lunar_cycle"

    def test_location_name_makes_unknown_locations_explicit(self):
        set_locale("en")
        world = World()

        assert world.location_name("loc_missing_ruin") == "Unknown location (loc_missing_ruin)"

    def test_location_state_from_dict_rejects_string_alias_payload(self):
        payload = World().to_dict()
        payload["grid"][0]["aliases"] = "The Crown City"

        try:
            World.from_dict(payload)
        except ValueError as exc:
            assert "aliases" in str(exc)
        else:
            raise AssertionError("Expected malformed aliases payload to fail fast")

    def test_from_dict_rejects_self_loop_route_in_serialized_topology(self):
        payload = World(width=1, height=1).to_dict()
        payload.pop("setting_bundle", None)
        payload["terrain_map"] = {
            "width": 1,
            "height": 1,
            "cells": [{"x": 0, "y": 0, "biome": "plains", "elevation": 128, "moisture": 128, "temperature": 128}],
        }
        payload["sites"] = [
            {
                "location_id": payload["grid"][0]["id"],
                "x": 0,
                "y": 0,
                "site_type": "city",
                "importance": 50,
            }
        ]
        payload["routes"] = [{
            "route_id": "route_loop",
            "from_site_id": payload["grid"][0]["id"],
            "to_site_id": payload["grid"][0]["id"],
            "route_type": "road",
            "distance": 1,
            "blocked": False,
        }]

        try:
            World.from_dict(payload)
        except ValueError as exc:
            assert "self-loop" in str(exc)
        else:
            raise AssertionError("Expected self-loop route to fail fast")

    def test_advance_calendar_position_respects_variable_month_lengths(self):
        world = World()
        world.setting_bundle = SettingBundle(
            schema_version=1,
            world_definition=WorldDefinition(
                world_key="custom",
                display_name="Custom World",
                lore_text="Custom lore",
                calendar=CalendarDefinition(
                    calendar_key="irregular",
                    display_name="Irregular Reckoning",
                    months=[
                        CalendarMonthDefinition("short", "Short", 10, season="winter"),
                        CalendarMonthDefinition("long", "Long", 40, season="spring"),
                    ],
                ),
            ),
        )

        month, day, year_delta = world.advance_calendar_position(1, 10, days=1)
        assert (month, day, year_delta) == (2, 1, 0)

        month, day, year_delta = world.advance_calendar_position(2, 40, days=1)
        assert (month, day, year_delta) == (1, 1, 1)

    def test_apply_calendar_definition_switches_active_calendar_immediately(self):
        world = World(year=1234)
        calendar = CalendarDefinition(
            calendar_key="starfall",
            display_name="Starfall Cycle",
            months=[
                CalendarMonthDefinition("wane", "Wane", 20, season="winter"),
                CalendarMonthDefinition("wax", "Wax", 25, season="summer"),
            ],
        )

        world.apply_calendar_definition(calendar, changed_year=1235, changed_month=2, changed_day=25)

        assert world.calendar_definition.calendar_key == "starfall"
        assert len(world.calendar_history) == 1
        assert world.calendar_history[0].year == 1235
        assert world.calendar_history[0].month == 2
        assert world.calendar_history[0].day == 25

    def test_calendar_definition_getter_returns_snapshot_not_live_reference(self):
        world = World()

        calendar = world.calendar_definition
        calendar.display_name = "Mutated Calendar"

        assert world.calendar_definition.display_name != "Mutated Calendar"

    def test_apply_calendar_definition_clones_input_calendar(self):
        world = World(year=1234)
        calendar = CalendarDefinition(
            calendar_key="starfall",
            display_name="Starfall Cycle",
            months=[
                CalendarMonthDefinition("wane", "Wane", 20, season="winter"),
                CalendarMonthDefinition("wax", "Wax", 25, season="summer"),
            ],
        )

        world.apply_calendar_definition(calendar)
        calendar.display_name = "Mutated Elsewhere"

        assert world.calendar_definition.display_name == "Starfall Cycle"

    def test_setting_bundle_assignment_preserves_calendar_history_when_calendar_is_unchanged(self):
        world = World(year=1234)
        world.apply_calendar_definition(
            CalendarDefinition(
                calendar_key="history",
                display_name="History",
                months=[CalendarMonthDefinition("beta", "Beta", 25, season="spring")],
            ),
            changed_year=1235,
            changed_month=1,
            changed_day=1,
        )

        world.setting_bundle = SettingBundle.from_dict(world.setting_bundle.to_dict())

        assert len(world.calendar_history) == 1
        assert world.calendar_history[0].calendar.calendar_key == "history"

    def test_setting_bundle_assignment_resets_calendar_history_when_calendar_changes(self):
        world = World(year=1234)
        world.apply_calendar_definition(
            CalendarDefinition(
                calendar_key="history",
                display_name="History",
                months=[CalendarMonthDefinition("beta", "Beta", 25, season="spring")],
            ),
            changed_year=1235,
            changed_month=1,
            changed_day=1,
        )
        world.setting_bundle = SettingBundle(
            schema_version=1,
            world_definition=WorldDefinition(
                world_key="custom",
                display_name="Custom World",
                lore_text="Custom lore",
                calendar=CalendarDefinition(
                    calendar_key="moonstep",
                    display_name="Moonstep",
                    months=[
                        CalendarMonthDefinition("arc", "Arc", 18, season="winter"),
                    ],
                ),
            ),
        )

        assert world.calendar_history == []
        assert world.calendar_baseline.calendar_key == "moonstep"

    def test_calendar_definition_by_key_returns_snapshot_for_baseline_and_history(self):
        world = World(year=1234)
        baseline = CalendarDefinition(
            calendar_key="baseline",
            display_name="Baseline",
            months=[
                CalendarMonthDefinition("alpha", "Alpha", 20, season="winter"),
            ],
        )
        history_calendar = CalendarDefinition(
            calendar_key="history",
            display_name="History",
            months=[
                CalendarMonthDefinition("beta", "Beta", 25, season="spring"),
            ],
        )
        world.calendar_baseline = CalendarDefinition.from_dict(baseline.to_dict())
        world.apply_calendar_definition(history_calendar, changed_year=1235, changed_month=1, changed_day=1)

        baseline_snapshot = world.calendar_definition_by_key("baseline")
        history_snapshot = world.calendar_definition_by_key("history")
        baseline_snapshot.display_name = "Mutated Baseline"
        history_snapshot.display_name = "Mutated History"

        assert world.calendar_baseline.display_name == "Baseline"
        assert world.calendar_history[0].calendar.display_name == "History"

    def test_calendar_definition_for_date_returns_snapshot(self):
        world = World(year=1234)
        calendar = CalendarDefinition(
            calendar_key="history",
            display_name="History",
            months=[
                CalendarMonthDefinition("beta", "Beta", 25, season="spring"),
            ],
        )
        world.apply_calendar_definition(calendar, changed_year=1235, changed_month=1, changed_day=1)

        snapshot = world.calendar_definition_for_date(1235, 1, 1)
        snapshot.display_name = "Mutated History"

        assert world.calendar_history[0].calendar.display_name == "History"

    def test_calendar_history_round_trips_with_world(self):
        world = World(year=1234)
        calendar = CalendarDefinition(
            calendar_key="moonstep",
            display_name="Moonstep",
            months=[
                CalendarMonthDefinition("arc", "Arc", 18, season="winter"),
                CalendarMonthDefinition("glow", "Glow", 18, season="spring"),
            ],
        )
        world.apply_calendar_definition(calendar, changed_year=1235, changed_month=2, changed_day=18)

        restored = World.from_dict(world.to_dict())

        assert len(restored.calendar_history) == 1
        assert restored.calendar_history[0].calendar.calendar_key == "moonstep"
        assert restored.calendar_history[0].day == 18

    def test_missing_season_metadata_falls_back_to_builtin_month_ordinal_policy(self):
        world = World()
        world.setting_bundle = SettingBundle(
            schema_version=1,
            world_definition=WorldDefinition(
                world_key="custom",
                display_name="Custom World",
                lore_text="Custom lore",
                calendar=CalendarDefinition(
                    calendar_key="seasonless",
                    display_name="Seasonless",
                    months=[
                        CalendarMonthDefinition("m1", "M1", 10),
                        CalendarMonthDefinition("m2", "M2", 10),
                        CalendarMonthDefinition("m3", "M3", 10),
                        CalendarMonthDefinition("m4", "M4", 10),
                        CalendarMonthDefinition("m5", "M5", 10),
                    ],
                ),
            ),
        )
        world.calendar_baseline = CalendarDefinition.from_dict(
            world.setting_bundle.world_definition.calendar.to_dict()
        )

        assert world.season_for_month(1) == "winter"
        assert world.season_for_month(3) == "spring"
        assert world.season_for_month(5) == "spring"

    def test_from_dict_rebuilds_recent_event_ids_from_event_records(self):
        from fantasy_simulator.events import WorldEventRecord

        world = World()
        payload = world.to_dict()
        payload["event_records"] = [
            WorldEventRecord(record_id="r1", kind="battle", year=1001, location_id="loc_thornwood").to_dict(),
            WorldEventRecord(record_id="r2", kind="journey", year=1002, location_id="loc_thornwood").to_dict(),
        ]
        payload["grid"][0]["recent_event_ids"] = ["stale"]
        payload["grid"][5]["recent_event_ids"] = ["stale", "wrong"]

        restored = World.from_dict(payload)

        thornwood = restored.get_location_by_id("loc_thornwood")
        assert thornwood is not None
        assert thornwood.recent_event_ids == ["r1", "r2"]

    def test_from_dict_rebuilds_compatibility_event_log_from_event_records_even_when_stale(self):
        from fantasy_simulator.events import WorldEventRecord

        world = World()
        payload = world.to_dict()
        payload["event_records"] = [
            WorldEventRecord(record_id="r1", kind="battle", year=1001, month=2, day=3, description="A clash").to_dict()
        ]
        payload["event_log"] = ["stale cache entry"]

        restored = World.from_dict(payload)

        assert restored.get_compatibility_event_log() == ["[Year 1001, Month 2, Day 3] A clash"]

    def test_compatibility_event_log_prefers_canonical_projection_over_stale_cache(self):
        from fantasy_simulator.events import WorldEventRecord

        world = World()
        world.event_log = ["stale cache entry"]
        world.record_event(
            WorldEventRecord(
                record_id="r1",
                kind="battle",
                year=1001,
                month=2,
                day=3,
                description="Canonical clash",
            )
        )
        world.event_log = ["stale cache entry"]

        assert world.get_compatibility_event_log() == ["[Year 1001, Month 2, Day 3] Canonical clash"]

    def test_event_log_property_projects_canonical_history_over_stale_cache(self):
        from fantasy_simulator.events import WorldEventRecord

        world = World()
        world.record_event(
            WorldEventRecord(
                record_id="r1",
                kind="battle",
                year=1001,
                month=2,
                day=3,
                description="Canonical clash",
            )
        )
        world.event_log = ["stale cache entry"]

        assert world.event_log == ["[Year 1001, Month 2, Day 3] Canonical clash"]

    def test_event_log_view_is_read_only(self):
        from fantasy_simulator.events import WorldEventRecord

        world = World()
        world.log_event("display-only line")
        with pytest.raises(TypeError):
            world.event_log.append("mutated")
        assert any("display-only line" in line for line in world.event_log)

        world.record_event(
            WorldEventRecord(
                record_id="r1",
                kind="battle",
                year=1001,
                description="Canonical clash",
            )
        )
        with pytest.raises(TypeError):
            world.event_log.append("mutated again")
        assert world.event_log == ["[Year 1001, Month 1, Day 1] Canonical clash"]

    def test_trimming_event_records_removes_dangling_recent_event_ids(self):
        from fantasy_simulator.events import WorldEventRecord

        world = World()
        world.MAX_EVENT_RECORDS = 2
        world.record_event(WorldEventRecord(record_id="r1", kind="battle", year=1001, location_id="loc_thornwood"))
        world.record_event(WorldEventRecord(record_id="r2", kind="battle", year=1001, location_id="loc_thornwood"))
        world.record_event(WorldEventRecord(record_id="r3", kind="battle", year=1001, location_id="loc_thornwood"))

        thornwood = world.get_location_by_id("loc_thornwood")
        assert thornwood is not None
        assert [record.record_id for record in world.event_records] == ["r2", "r3"]
        assert thornwood.recent_event_ids == ["r2", "r3"]


# ---------------------------------------------------------------------------
# State propagation decay — long-run saturation prevention
# ---------------------------------------------------------------------------

class TestStatePropagationDecay:
    def test_decay_reduces_inflated_state_in_isolation(self):
        """Decay alone should pull an inflated value toward baseline."""
        world = World()
        # Pick a location and inflate its danger well above baseline
        loc = None
        for candidate in world.grid.values():
            if candidate.region_type == "village":
                loc = candidate
                break
        assert loc is not None
        baseline = get_location_state_defaults(loc.id, loc.region_type)["danger"]
        loc.danger = 95
        # Call _decay_toward_baseline directly (no propagation)
        world._decay_toward_baseline()
        assert loc.danger < 95, (
            f"Decay did not reduce danger from 95; got {loc.danger}"
        )
        # Run more decay cycles
        for _ in range(30):
            world._decay_toward_baseline()
        # Should converge near baseline
        assert abs(loc.danger - baseline) <= 5, (
            f"danger={loc.danger} did not converge to baseline={baseline}"
        )

    def test_propagation_with_decay_stabilises(self):
        """With decay active, repeated propagation should stabilise
        rather than pushing all values to ceiling/floor."""
        world = World()
        # Record all danger values, run 50 cycles, check they don't all hit 100
        for _ in range(50):
            world.propagate_state()
        danger_values = [loc.danger for loc in world.grid.values()]
        # Not all locations should be at 100
        assert not all(d == 100 for d in danger_values), (
            "All locations saturated to danger=100"
        )
