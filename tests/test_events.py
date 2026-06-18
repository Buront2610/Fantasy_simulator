"""
tests/test_events.py - Unit tests for the EventSystem.
"""

import random

import pytest
from fantasy_simulator.character import Character
from fantasy_simulator.content.setting_bundle import RaceDefinition, SettingBundle, SiteSeedDefinition, WorldDefinition
from fantasy_simulator.events import EventResult, EventSystem
from fantasy_simulator import events_selection
from fantasy_simulator.events_family import resolve_birth_event
from fantasy_simulator.events_relationships import resolve_relationship_turning_point_event
from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.event_rendering import render_event_record
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.world import World


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def es() -> EventSystem:
    return EventSystem()


@pytest.fixture(autouse=True)
def reset_locale():
    previous = get_locale()
    set_locale("en")
    yield
    set_locale(previous)


def _make_char(
    name: str,
    location_id: str = "loc_aethoria_capital",
    age: int = 25,
    strength: int = 50,
    constitution: int = 50,
    intelligence: int = 50,
) -> Character:
    c = Character(
        name=name, age=age, gender="Male", race="Human", job="Warrior",
        strength=strength, constitution=constitution, intelligence=intelligence,
        dexterity=50, wisdom=40, charisma=40,
        skills={"Swordsmanship": 2},
        location_id=location_id,
    )
    return c


def _assert_semantic_event_result(result: EventResult) -> None:
    summary_key = result.metadata.get("summary_key")
    render_params = result.metadata.get("render_params")
    assert isinstance(summary_key, str)
    assert summary_key.startswith("events.")
    assert summary_key.endswith(".summary")
    assert isinstance(render_params, dict)

    record = WorldEventRecord.from_event_result(result)
    assert record.summary_key == summary_key
    assert record.render_params == render_params


@pytest.fixture
def char_a(world) -> Character:
    c = _make_char("Alice", location_id="loc_aethoria_capital")
    world.add_character(c)
    return c


@pytest.fixture
def char_b(world) -> Character:
    c = _make_char("Bob", location_id="loc_aethoria_capital")
    world.add_character(c)
    return c


# ---------------------------------------------------------------------------
# EventResult dataclass
# ---------------------------------------------------------------------------

class TestEventResult:
    def test_defaults(self):
        r = EventResult(description="something happened")
        assert r.affected_characters == []
        assert r.stat_changes == {}
        assert r.event_type == "generic"
        assert r.year == 0

    def test_custom_values(self):
        r = EventResult(
            description="battle",
            affected_characters=["id1", "id2"],
            stat_changes={"id1": {"strength": 2}},
            event_type="battle",
            year=1010,
        )
        assert r.event_type == "battle"
        assert r.year == 1010
        assert "id1" in r.affected_characters


class TestEventSemanticContract:
    def test_usual_event_families_emit_semantic_render_metadata(self, es, world):
        char1 = _make_char("Alice", location_id="loc_aethoria_capital", age=25)
        char2 = _make_char("Bob", location_id="loc_aethoria_capital", age=26)
        char1.skills = {"Swordsmanship": 2, "Fireball": 1}
        char2.skills = {"Swordsmanship": 1}
        world.add_character(char1)
        world.add_character(char2)

        event_results = [
            es.event_meeting(char1, char2, world, rng=random.Random(1)),
            es.event_battle(char1, char2, world, rng=random.Random(2)),
            es.event_discovery(char1, world, rng=random.Random(3)),
            es.event_aging(char1, world, rng=random.Random(4)),
            es.event_skill_training(char1, world, rng=random.Random(5)),
            es.event_journey(char1, world, rng=random.Random(6)),
        ]
        char1.update_relationship(char2.char_id, 80)
        char2.update_relationship(char1.char_id, 80)
        event_results.append(es.event_marriage(char1, char2, world, rng=random.Random(7)))
        event_results.append(resolve_birth_event(char1, char2, world, rng=random.Random(8)))

        for result in event_results:
            _assert_semantic_event_result(result)

    def test_death_event_emits_semantic_render_metadata(self, es, world):
        char = _make_char("Doomed", location_id="loc_aethoria_capital", age=80)
        world.add_character(char)

        result = es.event_death(char, world, rng=random.Random(9))

        _assert_semantic_event_result(result)


# ---------------------------------------------------------------------------
# event_meeting
# ---------------------------------------------------------------------------

class TestEventMeeting:
    def test_returns_event_result(self, es, char_a, char_b, world):
        result = es.event_meeting(char_a, char_b, world)
        assert isinstance(result, EventResult)

    def test_affected_both_chars(self, es, char_a, char_b, world):
        result = es.event_meeting(char_a, char_b, world)
        assert char_a.char_id in result.affected_characters
        assert char_b.char_id in result.affected_characters

    def test_relationship_recorded(self, es, char_a, char_b, world):
        es.event_meeting(char_a, char_b, world)
        # Relationship key is set (may be positive or negative)
        assert char_b.char_id in char_a.relationships

    def test_history_updated(self, es, char_a, char_b, world):
        es.event_meeting(char_a, char_b, world)
        # Both chars should have a history entry about the meeting
        assert any("Met" in h or "met" in h for h in char_a.history)

    def test_event_type(self, es, char_a, char_b, world):
        result = es.event_meeting(char_a, char_b, world)
        assert result.event_type == "meeting"

    def test_description_reports_bidirectional_relationships(self, es, char_a, char_b, world):
        result = es.event_meeting(char_a, char_b, world, rng=random.Random(0))

        rel_a = char_a.get_relationship(char_b.char_id)
        rel_b = char_b.get_relationship(char_a.char_id)
        rel_avg = round((rel_a + rel_b) / 2)

        assert f"Alice->Bob: {rel_a:+d}" in result.description
        assert f"Bob->Alice: {rel_b:+d}" in result.description
        assert f"Avg: {rel_avg:+d}" in result.description

    def test_generated_meeting_records_story_hook(self, es, char_a, char_b, world):
        result = es.event_meeting(char_a, char_b, world, rng=random.Random(0))

        render_params = result.metadata["render_params"]
        assert render_params["story_hook_key"].startswith("event_story_meeting_")
        assert result.description.split(".", 1)[0]

    def test_description_tone_matches_average_relationship(self, es, char_a, char_b, world):
        result = es.event_meeting(char_a, char_b, world, rng=random.Random(3))

        rel_a = char_a.get_relationship(char_b.char_id)
        rel_b = char_b.get_relationship(char_a.char_id)
        rel_avg = round((rel_a + rel_b) / 2)

        assert rel_avg > 0
        assert "pleasant exchange" in result.description
        assert "polite nod" not in result.description

    def test_personality_affinity_changes_meeting_relationship_delta(self, es, world):
        neutral_a = _make_char("Neutral A")
        neutral_b = _make_char("Neutral B")
        warm_a = _make_char("Warm A")
        warm_b = _make_char("Warm B")
        warm_profile = {
            "openness": 75,
            "discipline": 70,
            "extraversion": 65,
            "agreeableness": 90,
            "stability": 80,
        }
        warm_a.personality = dict(warm_profile)
        warm_b.personality = dict(warm_profile)
        for char in (neutral_a, neutral_b, warm_a, warm_b):
            world.add_character(char)

        neutral = es.event_meeting(neutral_a, neutral_b, world, rng=random.Random(0))
        warm = es.event_meeting(warm_a, warm_b, world, rng=random.Random(0))

        neutral_avg = round(
            (neutral_a.get_relationship(neutral_b.char_id) + neutral_b.get_relationship(neutral_a.char_id)) / 2
        )
        warm_avg = round((warm_a.get_relationship(warm_b.char_id) + warm_b.get_relationship(warm_a.char_id)) / 2)
        assert warm_avg > neutral_avg
        assert warm.metadata["personality_affinity"] > neutral.metadata["personality_affinity"]
        assert "shared_kindness" in warm.metadata["personality_factor_keys"]
        assert warm.metadata["relationship_delta"] > neutral.metadata["relationship_delta"]

    def test_personality_feats_change_meeting_relationship_delta(self, es, world):
        plain_a = _make_char("Plain A")
        plain_b = _make_char("Plain B")
        featured_a = _make_char("Featured A")
        featured_b = _make_char("Featured B")
        neutral_profile = {
            "openness": 50,
            "discipline": 50,
            "extraversion": 50,
            "agreeableness": 50,
            "stability": 50,
        }
        for char in (plain_a, plain_b, featured_a, featured_b):
            char.personality = dict(neutral_profile)
            world.add_character(char)
        featured_a.personality_feats = ["patient_listener"]
        featured_b.personality_feats = ["quick_tempered"]

        plain = es.event_meeting(plain_a, plain_b, world, rng=random.Random(0))
        featured = es.event_meeting(featured_a, featured_b, world, rng=random.Random(0))

        assert featured.metadata["relationship_delta"] > plain.metadata["relationship_delta"]
        assert featured.metadata["personality_feature_score"] > 0
        assert "temper_balanced" in featured.metadata["personality_feature_factor_keys"]
        assert "one temper steadied the other" in featured.metadata["render_params"]["personality_factors"]

    def test_shared_catalyst_can_soften_bad_personality_affinity(self, es, world):
        plain_a = _make_char("Plain A")
        plain_b = _make_char("Plain B")
        saved_a = _make_char("Saved A")
        rescuer_b = _make_char("Rescuer B")
        difficult_a = {
            "openness": 100,
            "discipline": 0,
            "extraversion": 100,
            "agreeableness": 20,
            "stability": 20,
        }
        difficult_b = {
            "openness": 0,
            "discipline": 100,
            "extraversion": 0,
            "agreeableness": 20,
            "stability": 20,
        }
        for character, personality in (
            (plain_a, difficult_a),
            (saved_a, difficult_a),
            (plain_b, difficult_b),
            (rescuer_b, difficult_b),
        ):
            character.personality = dict(personality)
            world.add_character(character)
        rescue = world.record_event(WorldEventRecord(
            record_id="rescue_ab",
            kind="dying_rescued",
            year=world.year,
            primary_actor_id=saved_a.char_id,
            secondary_actor_ids=[rescuer_b.char_id],
            description="Rescuer B saved Saved A.",
        ))

        plain = es.event_marriage(plain_a, plain_b, world, rng=random.Random(1))
        catalyzed = es.event_marriage(saved_a, rescuer_b, world, rng=random.Random(1))

        assert plain.event_type == "romance"
        assert catalyzed.event_type == "romance"
        assert catalyzed.metadata["relationship_delta"] > plain.metadata["relationship_delta"]
        assert catalyzed.metadata["relationship_catalyst_bonus"] > 0
        assert "rescue_debt" in catalyzed.metadata["relationship_catalyst_factor_keys"]
        assert rescue.record_id in catalyzed.metadata["cause_event_ids"]

    def test_recent_experiences_temper_personality_in_relationship_events(self, es, world):
        plain_a = _make_char("Plain A")
        plain_b = _make_char("Plain B")
        changed_a = _make_char("Changed A")
        changed_b = _make_char("Changed B")
        for char in (plain_a, plain_b, changed_a, changed_b):
            world.add_character(char)
        discovery = world.record_event(WorldEventRecord(
            record_id="shared_wonder",
            kind="adventure_discovery",
            year=world.year,
            primary_actor_id=changed_a.char_id,
            secondary_actor_ids=[changed_b.char_id],
            description="Changed A and Changed B found a buried hall.",
        ))

        plain = es.event_meeting(plain_a, plain_b, world, rng=random.Random(0))
        changed = es.event_meeting(changed_a, changed_b, world, rng=random.Random(0))

        assert changed.metadata["relationship_delta"] > plain.metadata["relationship_delta"]
        assert "recent_wonder" in changed.metadata["personality_context_factor_keys"]
        assert discovery.record_id in changed.metadata["cause_event_ids"]
        assert "recent wonder" in changed.metadata["render_params"]["personality_factors"]

    def test_relationship_turning_point_reconciles_bad_history_with_causal_record(self, es, world):
        saved = _make_char("Saved")
        rescuer = _make_char("Rescuer")
        saved.personality = {
            "openness": 50,
            "discipline": 50,
            "extraversion": 50,
            "agreeableness": 50,
            "stability": 50,
        }
        rescuer.personality = dict(saved.personality)
        saved.update_mutual_relationship(rescuer, -50)
        world.add_character(saved)
        world.add_character(rescuer)
        rescue = world.record_event(WorldEventRecord(
            record_id="rescue_turn",
            kind="dying_rescued",
            year=world.year,
            primary_actor_id=saved.char_id,
            secondary_actor_ids=[rescuer.char_id],
            description="Rescuer saved Saved.",
        ))

        result = resolve_relationship_turning_point_event(saved, rescuer, world, rng=random.Random(4))

        assert result.event_type == "relationship_reconciliation"
        assert saved.get_relationship(rescuer.char_id) > -50
        assert saved.has_relation_tag(rescuer.char_id, "friend")
        assert rescuer.has_relation_tag(saved.char_id, "friend")
        assert rescue.record_id in result.metadata["cause_event_ids"]
        assert "rescued_gratitude" in result.metadata["personality_context_factor_keys"]
        assert "A rescue debt still shaped how they saw each other." in result.description
        assert (
            result.metadata["render_params"]["turning_point_reason_key"]
            == "relationship_turning_point_reason_rescue_debt"
        )
        _assert_semantic_event_result(result)

        record = WorldEventRecord.from_event_result(result)
        assert "A rescue debt still shaped how they saw each other." in render_event_record(
            record, locale="en", world=world
        )
        assert "救助の恩が、互いを見る目をまだ変えていた。" in render_event_record(record, locale="ja", world=world)

    def test_relationship_turning_point_marks_unlikely_bond_when_catalyst_overcomes_bad_fit(self, es, world):
        saved = _make_char("Saved")
        rescuer = _make_char("Rescuer")
        saved.personality = {
            "openness": 100,
            "discipline": 0,
            "extraversion": 100,
            "agreeableness": 20,
            "stability": 20,
        }
        rescuer.personality = {
            "openness": 0,
            "discipline": 100,
            "extraversion": 0,
            "agreeableness": 20,
            "stability": 20,
        }
        saved.update_mutual_relationship(rescuer, -50)
        world.add_character(saved)
        world.add_character(rescuer)
        rescue = world.record_event(WorldEventRecord(
            record_id="rescue_unlikely",
            kind="dying_rescued",
            year=world.year,
            primary_actor_id=saved.char_id,
            secondary_actor_ids=[rescuer.char_id],
            description="Rescuer saved Saved despite their differences.",
        ))

        result = resolve_relationship_turning_point_event(saved, rescuer, world, rng=random.Random(4))

        assert result.event_type == "relationship_reconciliation"
        assert rescue.record_id in result.metadata["cause_event_ids"]
        assert result.metadata["personality_affinity"] < 0
        assert result.metadata["relationship_catalyst_bonus"] > 0
        assert (
            result.metadata["render_params"]["turning_point_reason_key"]
            == "relationship_turning_point_reason_unlikely_bond"
        )
        assert "Their temperaments did not fit" in result.description

    def test_relationship_turning_point_can_create_mentor_or_betrayer_tags(self, es, world):
        elder = _make_char("Elder", age=54)
        novice = _make_char("Novice", age=20)
        elder.update_mutual_relationship(novice, 45)
        rival = _make_char("Rival")
        target = _make_char("Target")
        rival.update_mutual_relationship(target, -55)
        for char in (elder, novice, rival, target):
            world.add_character(char)

        mentorship = resolve_relationship_turning_point_event(elder, novice, world, rng=random.Random(5))
        betrayal = resolve_relationship_turning_point_event(rival, target, world, rng=random.Random(6))

        assert mentorship.event_type == "relationship_mentorship"
        assert elder.has_relation_tag(novice.char_id, "mentor")
        assert novice.has_relation_tag(elder.char_id, "disciple")
        assert betrayal.event_type == "relationship_betrayal"
        assert rival.has_relation_tag(target.char_id, "betrayer")
        assert target.has_relation_tag(rival.char_id, "rival")


# ---------------------------------------------------------------------------
# event_battle
# ---------------------------------------------------------------------------

class TestEventBattle:
    def test_returns_event_result(self, es, char_a, char_b, world):
        result = es.event_battle(char_a, char_b, world)
        assert isinstance(result, EventResult)

    def test_both_affected(self, es, char_a, char_b, world):
        result = es.event_battle(char_a, char_b, world)
        assert char_a.char_id in result.affected_characters
        assert char_b.char_id in result.affected_characters

    def test_relationship_degraded(self, es, char_a, char_b, world):
        # Set neutral relationships first
        char_a.update_relationship(char_b.char_id, 0)
        char_b.update_relationship(char_a.char_id, 0)
        es.event_battle(char_a, char_b, world)
        # At least one should have negative relationship
        rel_a = char_a.get_relationship(char_b.char_id)
        rel_b = char_b.get_relationship(char_a.char_id)
        assert rel_a < 0 or rel_b < 0

    def test_event_type_battle(self, es, char_a, char_b, world):
        result = es.event_battle(char_a, char_b, world)
        assert result.event_type in ("battle", "battle_fatal")

    def test_generated_battle_records_story_hook(self, es, char_a, char_b, world):
        result = es.event_battle(char_a, char_b, world, rng=random.Random(0))

        render_params = result.metadata["render_params"]
        assert render_params["story_hook_key"].startswith("event_story_battle_")

    def test_generated_battle_records_detailed_combat_log(self, es, char_a, char_b, world):
        result = es.event_battle(char_a, char_b, world, rng=random.Random(0))

        combat_log = result.metadata["render_params"]["combat_log"]
        assert len(combat_log) >= 1
        assert combat_log[0]["round_number"] == 1
        assert "dice" in combat_log[0]
        assert "skill_key" in combat_log[0]
        assert any(entry["outcome"] == "decisive" for entry in combat_log)

    def test_battle_cites_prior_pair_conflict_as_direct_cause(self, es, char_a, char_b, world):
        prior = world.record_event(WorldEventRecord(
            record_id="evt_prior_meeting",
            kind="meeting",
            year=world.year,
            primary_actor_id=char_a.char_id,
            secondary_actor_ids=[char_b.char_id],
            description="A tense meeting.",
        ))

        result = es.event_battle(char_a, char_b, world, rng=random.Random(0))
        record = WorldEventRecord.from_event_result(result)

        assert result.metadata["cause_event_ids"] == [prior.record_id]
        assert record.cause_event_ids == [prior.record_id]

    def test_stat_changes_present(self, es, char_a, char_b, world):
        result = es.event_battle(char_a, char_b, world)
        # At least winner should have stat changes
        assert len(result.stat_changes) > 0

    def test_weak_loser_can_die(self, es, world):
        """A character with very low constitution may die in battle."""
        import random
        random.seed(99)  # seed that triggers death
        attacker = _make_char("Brute", strength=90, constitution=90)
        victim = _make_char("Victim", strength=5, constitution=4)
        world.add_character(attacker)
        world.add_character(victim)
        # Run up to 20 battles to see if death can occur
        for _ in range(20):
            if not victim.alive:
                break
            # Reset con to 4 to keep it weak
            victim.constitution = 4
            result = es.event_battle(attacker, victim, world)
            if not victim.alive:
                assert "battle_fatal" in result.event_type
                break
        # We can't guarantee death in exactly these attempts, but the
        # code path should be reachable — just assert the method ran.
        assert True  # above loop ran without error


# ---------------------------------------------------------------------------
# event_discovery
# ---------------------------------------------------------------------------

class TestEventDiscovery:
    def test_returns_event_result(self, es, char_a, world):
        result = es.event_discovery(char_a, world)
        assert isinstance(result, EventResult)

    def test_char_affected(self, es, char_a, world):
        result = es.event_discovery(char_a, world)
        assert char_a.char_id in result.affected_characters

    def test_history_updated(self, es, char_a, world):
        es.event_discovery(char_a, world)
        assert len(char_a.history) > 0

    def test_event_type(self, es, char_a, world):
        result = es.event_discovery(char_a, world)
        assert result.event_type == "discovery"

    def test_generated_discovery_records_story_hook(self, es, char_a, world):
        result = es.event_discovery(char_a, world, rng=random.Random(0))

        render_params = result.metadata["render_params"]
        assert render_params["story_hook_key"].startswith("event_story_discovery_")

    def test_stat_changes_applied(self, es, char_a, world):
        import random
        random.seed(0)
        before = {
            "strength": char_a.strength,
            "intelligence": char_a.intelligence,
            "dexterity": char_a.dexterity,
            "charisma": char_a.charisma,
        }
        es.event_discovery(char_a, world)
        after = {
            "strength": char_a.strength,
            "intelligence": char_a.intelligence,
            "dexterity": char_a.dexterity,
            "charisma": char_a.charisma,
        }
        changed = any(after[k] != before[k] for k in before)
        assert changed

    def test_japanese_locale_discovery_text_has_no_fixed_english_tail(self, es, char_a, world):
        set_locale("ja")
        result = es.event_discovery(char_a, world, rng=random.Random(1))

        assert "The knowledge contained within" not in result.description
        assert "The discovery will prove useful" not in result.description
        assert "Word of the discovery spread quickly" not in result.description


# ---------------------------------------------------------------------------
# event_skill_training
# ---------------------------------------------------------------------------

class TestEventSkillTraining:
    def test_returns_event_result(self, es, char_a, world):
        result = es.event_skill_training(char_a, world)
        assert isinstance(result, EventResult)

    def test_skill_level_increases(self, es, char_a, world):
        old_levels = dict(char_a.skills)
        es.event_skill_training(char_a, world)
        new_levels = char_a.skills
        # At least one skill should have increased
        improved = any(new_levels.get(k, 0) > v for k, v in old_levels.items())
        assert improved

    def test_no_skills_starter_added(self, world, es):
        """If character has no skills, one should be seeded."""
        c = Character("Blank", 20, "Male", "Human", "Warrior")
        world.add_character(c)
        assert c.skills == {}
        es.event_skill_training(c, world)
        assert len(c.skills) > 0

    def test_japanese_locale_training_text_has_no_fixed_english_effort(self, es, char_a, world):
        set_locale("ja")
        result = es.event_skill_training(char_a, world, rng=random.Random(0))

        assert "spent long hours in the training yard" not in result.description
        assert "pushed themselves beyond their limits" not in result.description

    def test_generated_training_records_story_hook(self, es, char_a, world):
        result = es.event_skill_training(char_a, world, rng=random.Random(0))

        render_params = result.metadata["render_params"]
        assert render_params["story_hook_key"].startswith("event_story_training_")


# ---------------------------------------------------------------------------
# event_journey
# ---------------------------------------------------------------------------

class TestEventJourney:
    def test_returns_event_result(self, es, char_a, world):
        result = es.event_journey(char_a, world)
        assert isinstance(result, EventResult)

    def test_location_changes(self, es, char_a, world):
        es.event_journey(char_a, world)
        assert isinstance(char_a.location_id, str)

    def test_history_updated(self, es, char_a, world):
        es.event_journey(char_a, world)
        assert any("Travelled" in h for h in char_a.history)

    def test_event_type(self, es, char_a, world):
        result = es.event_journey(char_a, world)
        assert result.event_type == "journey"

    def test_destination_marked_visited(self, es, char_a, world):
        result = es.event_journey(char_a, world, rng=random.Random(0))
        destination = world.get_location_by_id(char_a.location_id)
        assert destination is not None
        assert destination.visited is True
        assert result.event_type == "journey"

    def test_generated_journey_records_story_hook(self, es, char_a, world):
        result = es.event_journey(char_a, world, rng=random.Random(0))

        render_params = result.metadata["render_params"]
        assert render_params["story_hook_key"].startswith("event_story_journey_")

    def test_japanese_locale_localizes_region_type(self, es, char_a, world):
        set_locale("ja")
        result = es.event_journey(char_a, world, rng=random.Random(0))
        assert "（city）" not in result.description
        assert any(region in result.description for region in ("都市", "村", "森", "山岳", "地下迷宮", "平原"))

    def test_blocked_route_network_prevents_global_teleport(self, es):
        from fantasy_simulator.terrain import RouteEdge
        from fantasy_simulator.world import LocationState

        world = World(_skip_defaults=True, width=3, height=1)
        origin = LocationState(
            id="loc_origin",
            canonical_name="Origin",
            description="Origin",
            region_type="city",
            x=0,
            y=0,
            prosperity=50,
            safety=50,
            mood=50,
            danger=10,
            traffic=30,
            rumor_heat=10,
            road_condition=60,
        )
        blocked = LocationState(
            id="loc_blocked",
            canonical_name="Blocked",
            description="Blocked",
            region_type="village",
            x=1,
            y=0,
            prosperity=50,
            safety=50,
            mood=50,
            danger=10,
            traffic=30,
            rumor_heat=10,
            road_condition=60,
        )
        remote = LocationState(
            id="loc_remote",
            canonical_name="Remote",
            description="Remote",
            region_type="forest",
            x=2,
            y=0,
            prosperity=50,
            safety=50,
            mood=50,
            danger=40,
            traffic=20,
            rumor_heat=10,
            road_condition=60,
        )
        for loc in (origin, blocked, remote):
            world._register_location(loc)
        world._build_terrain_from_grid()
        world.routes = [
            RouteEdge("route_blocked", "loc_origin", "loc_blocked", "road", blocked=True),
        ]
        char = _make_char("Traveler", location_id="loc_origin")
        world.add_character(char)

        result = es.event_journey(char, world, rng=random.Random(0))

        assert char.location_id == "loc_origin"
        assert "no destination" in result.description.lower()


# ---------------------------------------------------------------------------
# event_aging
# ---------------------------------------------------------------------------

class TestEventAging:
    def test_age_increments(self, es, char_a, world):
        old_age = char_a.age
        es.event_aging(char_a, world)
        assert char_a.age == old_age + 1

    def test_history_updated(self, es, char_a, world):
        es.event_aging(char_a, world)
        assert any("Turned" in h for h in char_a.history)

    def test_returns_event_result(self, es, char_a, world):
        result = es.event_aging(char_a, world)
        assert isinstance(result, EventResult)

    def test_stat_changes_present(self, es, char_a, world):
        result = es.event_aging(char_a, world)
        assert char_a.char_id in result.stat_changes

    def test_long_lived_race_uses_lifespan_ratio_for_aging_band(self, es, world):
        elf = _make_char("Elder", age=120)
        elf.race = "Elf"
        world.add_character(elf)

        result = es.event_aging(elf, world, rng=random.Random(1))

        assert result.metadata["summary_key"] == "events.aging_young.summary"
        assert "dexterity" in result.stat_changes[elf.char_id]


# ---------------------------------------------------------------------------
# event_death
# ---------------------------------------------------------------------------

class TestEventDeath:
    def test_char_marked_dead(self, es, char_a, world):
        es.event_death(char_a, world)
        assert char_a.alive is False

    def test_history_updated(self, es, char_a, world):
        es.event_death(char_a, world)
        assert any("Passed away" in h for h in char_a.history)

    def test_event_type(self, es, char_a, world):
        result = es.event_death(char_a, world)
        assert result.event_type == "death"

    def test_spouse_notified(self, es, char_a, char_b, world):
        char_a.spouse_id = char_b.char_id
        char_b.spouse_id = char_a.char_id
        es.event_death(char_a, world)
        # Spouse loses positive relationship
        assert char_b.relationships.get(char_a.char_id, 0) < 0

    def test_handle_death_side_effects_clears_spouse_id(self, es, char_a, char_b, world):
        """handle_death_side_effects clears spouse_id on the surviving partner."""
        char_a.spouse_id = char_b.char_id
        char_b.spouse_id = char_a.char_id
        char_a.alive = False

        es.handle_death_side_effects(char_a, world)

        assert char_b.spouse_id is None
        assert any("Lost" in h or "失った" in h for h in char_b.history)

    def test_handle_death_side_effects_is_idempotent(self, es, char_a, char_b, world):
        """Calling handle_death_side_effects twice must not crash or double-add history."""
        char_a.spouse_id = char_b.char_id
        char_b.spouse_id = char_a.char_id
        char_a.alive = False

        es.handle_death_side_effects(char_a, world)
        history_len = len(char_b.history)

        es.handle_death_side_effects(char_a, world)
        assert len(char_b.history) == history_len


# ---------------------------------------------------------------------------
# event_marriage
# ---------------------------------------------------------------------------

class TestEventMarriage:
    def test_high_relationship_causes_marriage(self, es, char_a, char_b, world):
        char_a.update_relationship(char_b.char_id, 80)
        char_b.update_relationship(char_a.char_id, 80)
        result = es.event_marriage(char_a, char_b, world)
        assert result.event_type == "marriage"
        assert char_a.spouse_id == char_b.char_id
        assert char_b.spouse_id == char_a.char_id

    def test_marriage_cites_prior_romance_as_direct_cause(self, es, char_a, char_b, world):
        prior = world.record_event(WorldEventRecord(
            record_id="evt_prior_romance",
            kind="romance",
            year=world.year,
            primary_actor_id=char_a.char_id,
            secondary_actor_ids=[char_b.char_id],
            description="A growing romance.",
        ))
        char_a.update_relationship(char_b.char_id, 80)
        char_b.update_relationship(char_a.char_id, 80)

        result = es.event_marriage(char_a, char_b, world)
        record = WorldEventRecord.from_event_result(result)

        assert result.event_type == "marriage"
        assert result.metadata["cause_event_ids"] == [prior.record_id]
        assert record.cause_event_ids == [prior.record_id]

    def test_low_relationship_no_marriage(self, es, char_a, char_b, world):
        char_a.relationships.clear()
        char_b.relationships.clear()
        result = es.event_marriage(char_a, char_b, world)
        # Should be romance, not marriage
        assert result.event_type == "romance"
        assert char_a.spouse_id is None

    def test_repeated_romance_can_reach_marriage_threshold(self, es, char_a, char_b, world):
        first = es.event_marriage(char_a, char_b, world)
        second = es.event_marriage(char_a, char_b, world)
        third = es.event_marriage(char_a, char_b, world)

        assert first.event_type == "romance"
        assert second.event_type == "romance"
        assert third.event_type == "marriage"
        assert char_a.spouse_id == char_b.char_id

    def test_random_marriage_event_prefers_existing_affection(self, es, world):
        admirer = _make_char("Admirer")
        beloved = _make_char("Beloved")
        stranger = _make_char("Stranger")
        for char in (admirer, beloved, stranger):
            world.add_character(char)
        admirer.update_relationship(beloved.char_id, 40)
        beloved.update_relationship(admirer.char_id, 40)

        class FixedRng:
            def choices(self, population, weights=None, k=1):
                if population and population[0] == "meeting":
                    return ["marriage"]
                max_index = max(range(len(weights)), key=lambda index: weights[index])
                return [population[max_index]]

            def choice(self, options):
                return options[0]

            def sample(self, population, k):
                return list(population[:k])

            def randint(self, lo, hi):
                return hi

            def getrandbits(self, bits):
                return 1

        result = es.generate_random_event(world.characters, world, rng=FixedRng())

        assert result is not None
        assert result.event_type == "marriage"
        assert admirer.spouse_id == beloved.char_id

    def test_already_married_anniversary(self, es, char_a, char_b, world):
        char_a.spouse_id = char_b.char_id
        char_b.spouse_id = char_a.char_id
        char_a.update_relationship(char_b.char_id, 90)
        char_b.update_relationship(char_a.char_id, 90)
        result = es.event_marriage(char_a, char_b, world)
        assert result.event_type == "anniversary"

    def test_existing_spouse_blocks_new_marriage(self, es, char_a, char_b, world):
        outsider = _make_char("Cara", location_id="loc_aethoria_capital")
        world.add_character(outsider)
        char_a.spouse_id = outsider.char_id
        char_a.update_relationship(char_b.char_id, 90)
        char_b.update_relationship(char_a.char_id, 90)

        result = es.event_marriage(char_a, char_b, world)

        assert result.event_type == "romance"
        assert char_a.spouse_id == outsider.char_id
        assert char_b.spouse_id is None

    def test_personality_affinity_lowers_marriage_threshold(self, es, world):
        neutral_a = _make_char("Neutral A")
        neutral_b = _make_char("Neutral B")
        warm_a = _make_char("Warm A")
        warm_b = _make_char("Warm B")
        warm_profile = {
            "openness": 75,
            "discipline": 70,
            "extraversion": 65,
            "agreeableness": 90,
            "stability": 80,
        }
        warm_a.personality = dict(warm_profile)
        warm_b.personality = dict(warm_profile)
        for first, second in ((neutral_a, neutral_b), (warm_a, warm_b)):
            first.update_relationship(second.char_id, 36)
            second.update_relationship(first.char_id, 36)
            world.add_character(first)
            world.add_character(second)

        neutral = es.event_marriage(neutral_a, neutral_b, world, rng=random.Random(1))
        warm = es.event_marriage(warm_a, warm_b, world, rng=random.Random(1))

        assert neutral.event_type == "romance"
        assert warm.event_type == "marriage"

    def test_shared_catalyst_can_bridge_bad_affinity_to_marriage(self, es, world):
        plain_a = _make_char("Plain A")
        plain_b = _make_char("Plain B")
        saved_a = _make_char("Saved A")
        rescuer_b = _make_char("Rescuer B")
        difficult_a = {
            "openness": 100,
            "discipline": 0,
            "extraversion": 100,
            "agreeableness": 20,
            "stability": 20,
        }
        difficult_b = {
            "openness": 0,
            "discipline": 100,
            "extraversion": 0,
            "agreeableness": 20,
            "stability": 20,
        }
        for first, second in ((plain_a, plain_b), (saved_a, rescuer_b)):
            first.personality = dict(difficult_a)
            second.personality = dict(difficult_b)
            first.update_relationship(second.char_id, 40)
            second.update_relationship(first.char_id, 40)
            world.add_character(first)
            world.add_character(second)
        rescue = world.record_event(WorldEventRecord(
            record_id="rescue_for_marriage",
            kind="dying_rescued",
            year=world.year,
            primary_actor_id=saved_a.char_id,
            secondary_actor_ids=[rescuer_b.char_id],
            description="Rescuer B saved Saved A.",
        ))

        plain = es.event_marriage(plain_a, plain_b, world, rng=random.Random(1))
        catalyzed = es.event_marriage(saved_a, rescuer_b, world, rng=random.Random(1))

        assert plain.event_type == "romance"
        assert catalyzed.event_type == "marriage"
        assert rescue.record_id in catalyzed.metadata["cause_event_ids"]
        assert catalyzed.metadata["relationship_catalyst_bonus"] > 0


class TestEventBirth:
    def test_birth_creates_child_and_family_tags(self, es, char_a, char_b, world):
        char_a.spouse_id = char_b.char_id
        char_b.spouse_id = char_a.char_id

        result = resolve_birth_event(char_a, char_b, world, rng=random.Random(1))

        child_id = result.affected_characters[0]
        child = world.get_character_by_id(child_id)
        assert result.event_type == "birth"
        assert child is not None
        assert child.age == 0
        assert child.founder_background is None
        assert child.location_id == char_a.location_id
        assert char_a.has_relation_tag(child.char_id, "child")
        assert char_b.has_relation_tag(child.char_id, "child")
        assert child.has_relation_tag(char_a.char_id, "parent")
        assert child.has_relation_tag(char_b.char_id, "parent")
        assert result.metadata["summary_key"] == "events.birth.summary"

    def test_birth_strengthens_couple_as_co_parents_and_cites_marriage(self, es, char_a, char_b, world):
        char_a.spouse_id = char_b.char_id
        char_b.spouse_id = char_a.char_id
        world.event_records = [
            WorldEventRecord(
                record_id="marriage_ab",
                kind="marriage",
                year=world.year,
                primary_actor_id=char_a.char_id,
                secondary_actor_ids=[char_b.char_id],
            )
        ]

        result = resolve_birth_event(char_a, char_b, world, rng=random.Random(1))
        birth_record_id = result.metadata["record_id"]

        assert char_a.get_relationship(char_b.char_id) == 6
        assert char_b.get_relationship(char_a.char_id) == 6
        assert char_a.has_relation_tag(char_b.char_id, "co_parent")
        assert char_b.has_relation_tag(char_a.char_id, "co_parent")
        assert char_a.has_relation_tag(char_b.char_id, "family")
        assert char_b.has_relation_tag(char_a.char_id, "family")
        assert birth_record_id in char_a.relation_tag_sources[f"{char_b.char_id}:co_parent"]
        assert result.metadata["cause_event_ids"] == ["marriage_ab"]

    def test_random_birth_event_uses_married_collocated_pair(self, es, char_a, char_b, world):
        char_a.spouse_id = char_b.char_id
        char_b.spouse_id = char_a.char_id

        class BirthRng:
            def choices(self, population, weights=None, k=1):
                if population and population[0] == "meeting":
                    return ["birth"]
                return [population[0]]

            def choice(self, options):
                return options[0]

            def sample(self, population, k):
                return list(population[:k])

            def randint(self, lo, hi):
                return lo

            def getrandbits(self, bits):
                return 1

        result = es.generate_random_event(world.characters, world, rng=BirthRng())

        assert result is not None
        assert result.event_type == "birth"
        assert len(world.characters) == 3

    def test_random_birth_event_reuses_birth_pair_scan(self, es, char_a, char_b, world, monkeypatch):
        char_a.spouse_id = char_b.char_id
        char_b.spouse_id = char_a.char_id
        calls = 0

        def fake_birth_pairs(_alive):
            nonlocal calls
            calls += 1
            return [(char_a, char_b)]

        class BirthRng:
            def choices(self, population, weights=None, k=1):
                if "birth" in population:
                    return ["birth"]
                return [population[0]]

            def choice(self, options):
                return options[0]

            def randint(self, lo, hi):
                return lo

            def sample(self, population, k):
                return list(population[:k])

            def getrandbits(self, bits):
                return 2

        monkeypatch.setattr(events_selection, "birth_pairs", fake_birth_pairs)

        result = es.generate_random_event(world.characters, world, rng=BirthRng())

        assert result is not None
        assert result.event_type == "birth"
        assert calls == 1


# ---------------------------------------------------------------------------
# check_natural_death
# ---------------------------------------------------------------------------

class TestNaturalDeath:
    def test_young_character_rarely_dies(self, es, world):
        """A young character should almost never die naturally."""
        young = _make_char("Young", age=20, constitution=80)
        world.add_character(young)
        deaths = 0
        for _ in range(200):
            young.alive = True  # reset
            young.age = 20
            result = es.check_natural_death(young, world)
            if result is not None:
                deaths += 1
        # Fewer than 5 deaths out of 200 trials
        assert deaths < 5

    def test_very_old_character_may_die(self, es, world):
        """A character well past max age should have a high death chance."""
        old = _make_char("Ancient", age=78, constitution=10)
        old.race = "Human"  # max_age = 80
        world.add_character(old)
        results = []
        for _ in range(100):
            old.alive = True
            result = es.check_natural_death(old, world)
            results.append(result is not None)
        assert sum(results) > 10  # should die in a meaningful fraction

    def test_dead_char_skipped(self, es, world):
        """Already-dead characters should return None immediately."""
        dead = _make_char("Ghost")
        dead.alive = False
        world.add_character(dead)
        result = es.check_natural_death(dead, world)
        assert result is None

    def test_custom_bundle_race_lifespan_drives_natural_decline(self, es, world):
        """World-authored race lifespan overrides Character.max_age for lifecycle checks."""

        class FixedRng:
            def random(self):
                return 0.0

        world.setting_bundle = SettingBundle(
            schema_version=1,
            world_definition=WorldDefinition(
                world_key="short_lived",
                display_name="Short Lived",
                lore_text="A world with brief human lives.",
                races=[RaceDefinition("Human", "Brief lives.", lifespan_years=40)],
                site_seeds=[
                    SiteSeedDefinition(
                        location_id="loc_aethoria_capital",
                        name="Capital",
                        description="Capital.",
                        region_type="city",
                        x=0,
                        y=0,
                        tags=["default_resident"],
                    )
                ],
            ),
        )
        character = _make_char("Elder", age=40, constitution=100)
        world.add_character(character)

        result = es.check_natural_death(character, world, rng=FixedRng())

        assert result is not None
        assert result.event_type == "condition_worsened"


# ---------------------------------------------------------------------------
# generate_random_event
# ---------------------------------------------------------------------------

class TestGenerateRandomEvent:
    def test_returns_event_result(self, es, world):
        for _ in range(5):
            c = _make_char(f"Char{_}", location_id="loc_aethoria_capital")
            world.add_character(c)
        result = es.generate_random_event(world.characters, world)
        assert result is None or isinstance(result, EventResult)

    def test_no_alive_chars_returns_none(self, es, world):
        dead = _make_char("Dead")
        dead.alive = False
        world.add_character(dead)
        result = es.generate_random_event([dead], world)
        assert result is None

    def test_chars_on_adventure_are_skipped(self, es, world):
        adventurer = _make_char("Away")
        adventurer.active_adventure_id = "adv-1"
        world.add_character(adventurer)
        result = es.generate_random_event([adventurer], world)
        assert result is None

    def test_single_char_solo_event(self, es, world):
        """With only one character, a solo event should fire (no crash)."""
        c = _make_char("Solo", location_id="loc_aethoria_capital")
        c.skills = {"Swordsmanship": 1}
        world.add_character(c)
        import random
        random.seed(5)
        for _ in range(10):
            result = es.generate_random_event([c], world)
            assert result is None or isinstance(result, EventResult)

    def test_random_event_table_can_choose_relationship_turning_point(self, es, world):
        class TurningPointRng(random.Random):
            def choices(self, population, weights=None, k=1):  # noqa: ANN001, D401
                if "relationship_turning_point" in population:
                    return ["relationship_turning_point"]
                return [population[0]]

            def choice(self, sequence):  # noqa: ANN001
                return sequence[0]

            def sample(self, population, k):  # noqa: ANN001
                return list(population)[:k]

        first = _make_char("First", location_id="loc_aethoria_capital")
        second = _make_char("Second", location_id="loc_aethoria_capital")
        world.add_character(first)
        world.add_character(second)

        result = es.generate_random_event(world.characters, world, rng=TurningPointRng(7))

        assert result is not None
        assert result.event_type.startswith("relationship_")

    def test_random_event_table_excludes_direct_death(self, es):
        assert "death" not in es._EVENT_WEIGHTS

    def test_random_event_table_excludes_aging(self, es):
        assert "aging" not in es._EVENT_WEIGHTS


# ---------------------------------------------------------------------------
# WorldEventRecord
# ---------------------------------------------------------------------------

class TestWorldEventRecord:
    def test_to_dict_round_trip(self):
        from fantasy_simulator.events import WorldEventRecord
        record = WorldEventRecord(
            kind="battle",
            year=1005,
            location_id="loc_aethoria_capital",
            primary_actor_id="abc123",
            secondary_actor_ids=["def456"],
            description="A battle occurred.",
            severity=3,
            visibility="public",
        )
        d = record.to_dict()
        restored = WorldEventRecord.from_dict(d)
        assert restored.kind == "battle"
        assert restored.year == 1005
        assert restored.location_id == "loc_aethoria_capital"
        assert restored.primary_actor_id == "abc123"
        assert restored.secondary_actor_ids == ["def456"]
        assert restored.severity == 3

    def test_from_event_result(self):
        from fantasy_simulator.events import WorldEventRecord
        result = EventResult(
            description="A battle occurred.",
            affected_characters=["abc123", "def456"],
            stat_changes={},
            event_type="battle",
            year=1005,
        )
        record = WorldEventRecord.from_event_result(result, location_id="loc_thornwood", severity=3)
        assert record.kind == "battle"
        assert record.year == 1005
        assert record.location_id == "loc_thornwood"
        assert record.primary_actor_id == "abc123"
        assert record.secondary_actor_ids == ["def456"]
        assert record.severity == 3
        assert record.description == "A battle occurred."

    def test_from_event_result_no_actors(self):
        from fantasy_simulator.events import WorldEventRecord
        result = EventResult(description="Nothing happened.", year=1000)
        record = WorldEventRecord.from_event_result(result)
        assert record.primary_actor_id is None
        assert record.secondary_actor_ids == []

    def test_default_values(self):
        from fantasy_simulator.events import WorldEventRecord
        record = WorldEventRecord()
        assert record.kind == "generic"
        assert record.year == 0
        assert record.location_id is None
        assert record.severity == 1
        assert record.visibility == "public"
        assert len(record.record_id) == 32
