"""
tests/test_world.py - Unit tests for the World class.
"""

from character import Character
from i18n import set_locale
from world import World


def _make_char(name="Aldric", location="Aethoria Capital"):
    return Character(name=name, age=25, gender="Male", race="Human", job="Warrior", location=location)


class TestWorld:
    def test_render_map_contains_header(self):
        set_locale("en")
        world = World()
        rendered = world.render_map()
        assert "WORLD MAP" in rendered
        assert "Aethoria" in rendered

    def test_render_map_uses_highlight_marker(self):
        world = World()
        rendered = world.render_map(highlight_location="Aethoria Capital")
        assert "*" in rendered

    def test_get_neighboring_locations_returns_adjacent_cells(self):
        world = World()
        neighbors = world.get_neighboring_locations("Aethoria Capital")
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
        chars = world.get_characters_at_location("Aethoria Capital")
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
