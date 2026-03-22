"""
tests/test_world.py - Unit tests for the World class.
"""

import unicodedata

from character import Character
from i18n import set_locale
from world import Location, World


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

    def test_locations_have_state_defaults(self):
        world = World()
        capital = world.get_location_by_id("loc_aethoria_capital")
        assert capital is not None
        assert capital.canonical_name == "Aethoria Capital"
        assert capital.prosperity == 85
        assert capital.safety == 80
        assert capital.danger == 15

    def test_location_backward_compatible_constructor_accepts_name(self):
        location = Location(
            id="loc_custom_city",
            name="Custom City",
            description="A custom settlement.",
            region_type="city",
            x=1,
            y=1,
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
        from events import WorldEventRecord
        world = World()
        record = WorldEventRecord(kind="battle", year=1001, location_id="loc_aethoria_capital")
        world.record_event(record)
        assert len(world.event_records) == 1
        assert world.event_records[0].kind == "battle"

    def test_get_events_by_location(self):
        from events import WorldEventRecord
        world = World()
        world.record_event(WorldEventRecord(kind="battle", year=1001, location_id="loc_thornwood"))
        world.record_event(WorldEventRecord(kind="meeting", year=1001, location_id="loc_aethoria_capital"))
        world.record_event(WorldEventRecord(kind="discovery", year=1002, location_id="loc_thornwood"))
        results = world.get_events_by_location("loc_thornwood")
        assert len(results) == 2
        assert all(r.location_id == "loc_thornwood" for r in results)

    def test_get_events_by_actor(self):
        from events import WorldEventRecord
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
        from events import WorldEventRecord
        world = World()
        world.record_event(WorldEventRecord(kind="battle", year=1001))
        world.record_event(WorldEventRecord(kind="meeting", year=1002))
        world.record_event(WorldEventRecord(kind="journey", year=1001))
        assert len(world.get_events_by_year(1001)) == 2
        assert len(world.get_events_by_year(1002)) == 1

    def test_event_records_in_to_dict_round_trip(self):
        from events import WorldEventRecord
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

    def test_trimming_event_records_removes_dangling_recent_event_ids(self):
        from events import WorldEventRecord

        world = World()
        world.MAX_EVENT_RECORDS = 2
        world.record_event(WorldEventRecord(record_id="r1", kind="battle", year=1001, location_id="loc_thornwood"))
        world.record_event(WorldEventRecord(record_id="r2", kind="battle", year=1001, location_id="loc_thornwood"))
        world.record_event(WorldEventRecord(record_id="r3", kind="battle", year=1001, location_id="loc_thornwood"))

        thornwood = world.get_location_by_id("loc_thornwood")
        assert thornwood is not None
        assert [record.record_id for record in world.event_records] == ["r2", "r3"]
        assert thornwood.recent_event_ids == ["r2", "r3"]
