"""
Tests for the structured relationship system (design §7.4).

Covers:
- Relation tag CRUD operations
- Tag assignment during events (battle → rival, meeting → friend, marriage → spouse)
- Serialization round-trip
- Tag-based narrative differentiation
"""
import random

import pytest

from character import Character
from events import EventSystem
from world import World


@pytest.fixture
def world():
    return World(name="TestWorld", year=1000)


@pytest.fixture
def event_system():
    return EventSystem()


def _make_char(name="Test", **kwargs):
    defaults = dict(
        age=25, gender="male", race="Human", job="Warrior",
        strength=50, intelligence=50, dexterity=50,
        wisdom=50, charisma=50, constitution=50,
        char_id=name.lower()[:8],
    )
    defaults.update(kwargs)
    return Character(name=name, **defaults)


class TestRelationTagBasics:
    """Emily Short: Relation tags must be robust and idempotent."""

    def test_add_tag(self):
        char = _make_char()
        char.add_relation_tag("other_id", "friend")
        assert char.has_relation_tag("other_id", "friend")

    def test_add_tag_idempotent(self):
        char = _make_char()
        char.add_relation_tag("other_id", "friend")
        char.add_relation_tag("other_id", "friend")
        assert char.get_relation_tags("other_id") == ["friend"]

    def test_multiple_tags(self):
        char = _make_char()
        char.add_relation_tag("other_id", "friend")
        char.add_relation_tag("other_id", "savior")
        tags = char.get_relation_tags("other_id")
        assert "friend" in tags
        assert "savior" in tags
        assert len(tags) == 2

    def test_no_tags_returns_empty(self):
        char = _make_char()
        assert char.get_relation_tags("unknown") == []
        assert char.has_relation_tag("unknown", "friend") is False


class TestRelationTagSerialization:
    """Bob Nystrom: Serialization must preserve relation tags."""

    def test_round_trip(self):
        char = _make_char()
        char.add_relation_tag("abc123", "friend")
        char.add_relation_tag("abc123", "savior")
        char.add_relation_tag("def456", "rival")
        data = char.to_dict()
        restored = Character.from_dict(data)
        assert restored.has_relation_tag("abc123", "friend")
        assert restored.has_relation_tag("abc123", "savior")
        assert restored.has_relation_tag("def456", "rival")

    def test_old_save_without_relation_tags(self):
        """Backward compat: old saves without relation_tags load with empty dict."""
        data = {
            "name": "Old", "age": 30, "gender": "male",
            "race": "Human", "job": "Warrior",
        }
        char = Character.from_dict(data)
        assert char.relation_tags == {}


class TestRelationTagsFromEvents:
    """Tarn Adams: Events should build relationship history through tags."""

    def test_battle_creates_rival_tags(self, world, event_system):
        char1 = _make_char("Fighter1", strength=80, char_id="fight001")
        char2 = _make_char("Fighter2", strength=20, char_id="fight002")
        world.add_character(char1)
        world.add_character(char2)
        rng = random.Random(42)
        event_system.event_battle(char1, char2, world, rng=rng)
        assert char1.has_relation_tag(char2.char_id, "rival")
        assert char2.has_relation_tag(char1.char_id, "rival")

    def test_marriage_creates_spouse_tags(self, world, event_system):
        char1 = _make_char("Bride", age=25, char_id="bride001")
        char2 = _make_char("Groom", age=25, char_id="groom001")
        # Set high mutual affection to trigger marriage
        char1.update_relationship(char2.char_id, 80)
        char2.update_relationship(char1.char_id, 80)
        world.add_character(char1)
        world.add_character(char2)
        rng = random.Random(42)
        result = event_system.event_marriage(char1, char2, world, rng=rng)
        assert result.event_type == "marriage"
        assert char1.has_relation_tag(char2.char_id, "spouse")
        assert char2.has_relation_tag(char1.char_id, "spouse")

    def test_positive_meeting_creates_friend_tags(self, world, event_system):
        char1 = _make_char("Friendly1", char_id="frien001")
        char2 = _make_char("Friendly2", char_id="frien002")
        # Pre-set high affinity so meeting stays positive
        char1.update_relationship(char2.char_id, 60)
        char2.update_relationship(char1.char_id, 60)
        world.add_character(char1)
        world.add_character(char2)
        # Run multiple meetings until friend tag is assigned
        tagged = False
        for seed in range(100):
            rng = random.Random(seed)
            event_system.event_meeting(char1, char2, world, rng=rng)
            if char1.has_relation_tag(char2.char_id, "friend"):
                tagged = True
                break
        assert tagged, "Expected friend tag after positive meetings"
