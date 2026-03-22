"""
tests/test_world.py - Unit tests for the World class.
"""

from character import Character
from i18n import set_locale
from world import World


def _make_char(name="Aldric", location_id="loc_aethoria_capital"):
    return Character(
        name=name, age=25, gender="Male", race="Human", job="Warrior", location_id=location_id,
    )


class TestWorld:
    def test_render_map_contains_header(self):
        set_locale("en")
        world = World()
        rendered = world.render_map()
        assert "WORLD MAP" in rendered
        assert "Aethoria" in rendered

    def test_render_map_uses_highlight_marker(self):
        world = World()
        rendered = world.render_map(highlight_location="loc_aethoria_capital")
        assert "*" in rendered

    def test_get_neighboring_locations_returns_adjacent_cells(self):
        world = World()
        neighbors = world.get_neighboring_locations("loc_aethoria_capital")
        assert neighbors
        assert all(hasattr(loc, "name") for loc in neighbors)

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
