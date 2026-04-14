"""
tests/test_world.py - Unit tests for the World class.
"""

import unicodedata

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
from fantasy_simulator.world import LocationState, World
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

    def test_add_character_marks_location_visited(self):
        world = World()
        capital = world.get_location_by_id("loc_aethoria_capital")
        assert capital is not None
        assert capital.visited is False
        world.add_character(_make_char())
        assert capital.visited is True

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
        world.grid.clear()
        world._location_id_index.clear()
        world._location_name_index.clear()
        world._build_default_map()

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
        world.grid.clear()
        world._location_id_index.clear()
        world._location_name_index.clear()
        world._build_default_map()
        payload = world.to_dict()
        payload["grid"][0].pop("id")

        restored = World.from_dict(payload)

        location = restored.get_location_by_id("hub_primary")
        assert location is not None
        assert location.canonical_name == "Clockwork Hub"

    def test_default_world_uses_bundle_site_seeds(self):
        world = World(width=2, height=1)

        expected_entries = [
            seed.as_world_data_entry()
            for seed in world.setting_bundle.world_definition.site_seeds
            if seed.x < 2 and seed.y < 1
        ]

        assert world.default_location_entries()[:len(expected_entries)] == expected_entries
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

    def test_custom_calendar_round_trips_with_world(self):
        world = World()
        world.setting_bundle = SettingBundle(
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

        restored = World.from_dict(world.to_dict())

        assert restored.months_per_year == 2
        assert restored.days_in_month(1) == 20
        assert restored.days_in_month(2) == 35
        assert restored.season_for_month(2) == "summer"

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
