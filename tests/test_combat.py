from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from fantasy_simulator.character import Character
from fantasy_simulator.combat_system.resolution import SPELL_EFFECTS, resolve_combat


def _make_char(name: str, *, strength: int, constitution: int) -> Character:
    return Character(
        name=name,
        age=25,
        gender="Male",
        race="Human",
        job="Warrior",
        strength=strength,
        constitution=constitution,
        intelligence=30,
        dexterity=30,
        wisdom=20,
        charisma=20,
        skills={"Swordsmanship": 2},
        char_id=name.lower(),
    )


def _make_mage(name: str) -> Character:
    return Character(
        name=name,
        age=25,
        gender="Female",
        race="Elf",
        job="Mage",
        strength=25,
        constitution=45,
        intelligence=90,
        dexterity=40,
        wisdom=70,
        charisma=30,
        skills={"Fireball": 4, "Mana Control": 3},
        char_id=name.lower(),
    )


def test_resolve_combat_returns_standalone_resolution_without_mutating_combatants() -> None:
    alice = _make_char("Alice", strength=80, constitution=70)
    bob = _make_char("Bob", strength=20, constitution=30)
    original_stats = (alice.strength, alice.constitution, bob.strength, bob.constitution)

    resolution = resolve_combat(alice, bob, random.Random(0))

    assert resolution.winner is alice
    assert resolution.loser is bob
    assert (alice.strength, alice.constitution, bob.strength, bob.constitution) == original_stats
    assert len(resolution.log_entries) >= 1
    assert any(entry.outcome == "decisive" for entry in resolution.log_entries)


def test_combat_log_payload_is_json_ready() -> None:
    alice = _make_char("Alice", strength=80, constitution=70)
    bob = _make_char("Bob", strength=20, constitution=30)

    payload = resolve_combat(alice, bob, random.Random(1)).combat_log_payload()

    assert payload[0]["round_number"] == 1
    assert payload[0]["actor_id"] in {"alice", "bob"}
    assert isinstance(payload[0]["attack_total"], int)
    assert {"action_kind", "skill_key", "dice", "modifier", "target_number", "damage"} <= set(payload[0])


def test_combat_uses_spell_effects_and_skill_modifiers() -> None:
    mage = _make_mage("Mira")
    guard = _make_char("Guard", strength=45, constitution=50)

    resolution = resolve_combat(mage, guard, random.Random(2))
    payload = resolution.combat_log_payload()

    assert "Fireball" in SPELL_EFFECTS
    assert any(entry["skill_key"] == "Fireball" for entry in payload)
    assert any(entry["action_kind"] == "spell_attack" for entry in payload)


def test_incapacitation_takes_precedence_over_higher_base_power() -> None:
    mage = SimpleNamespace(
        char_id="mage", name="Mage", constitution=10, dexterity=200, intelligence=200,
        wisdom=100, combat_power=10, skills={"Fireball": 20},
    )
    brute = SimpleNamespace(
        char_id="brute", name="Brute", constitution=10, dexterity=10, intelligence=10,
        wisdom=10, combat_power=500, skills={},
    )

    result = resolve_combat(mage, brute, random.Random(0))

    assert result.log_entries[-1].target_vitality == 0
    assert result.winner is mage
    assert result.loser is brute
    assert result.end_reason == "incapacitation"
    assert result.state_for(brute.char_id).remaining_vitality == 0
    assert result.state_for(mage.char_id).damage_taken == 0


@pytest.mark.parametrize(
    "skill", ["Arcane Shield", "Divine Shield", "Evasion", "Shield Block", "Heavy Armor", "Endurance"],
)
def test_defensive_skills_are_not_selected_as_attacks(skill: str) -> None:
    guard = _make_char("Guard", strength=50, constitution=60)
    guard.skills = {skill: 10, "Swordsmanship": 1}
    opponent = _make_char("Opponent", strength=50, constitution=60)

    result = resolve_combat(guard, opponent, random.Random(8))

    attacks = [entry for entry in result.log_entries if entry.actor_id == guard.char_id]
    assert attacks
    assert all(entry.skill_key == "Swordsmanship" for entry in attacks)


def test_defensive_training_improves_defense_without_changing_attacks() -> None:
    guard = _make_char("Guard", strength=50, constitution=60)
    opponent = _make_char("Opponent", strength=50, constitution=60)
    baseline = resolve_combat(guard, opponent, random.Random(8))
    guard.skills["Arcane Shield"] = 4
    trained = resolve_combat(guard, opponent, random.Random(8))

    before = next(entry for entry in baseline.log_entries if entry.target_id == guard.char_id)
    after = next(entry for entry in trained.log_entries if entry.target_id == guard.char_id)
    assert after.defense_total > before.defense_total


def test_equal_skill_levels_use_stable_key_order() -> None:
    from fantasy_simulator.combat_system.resolution import _best_skill

    char = _make_char("Guard", strength=50, constitution=60)
    char.skills = {"Swordsmanship": 2, "Archery": 2}

    assert _best_skill(char, ["Swordsmanship", "Archery"]) == "Archery"
    assert _best_skill(char, ["Archery", "Swordsmanship"]) == "Archery"


def test_equal_initiative_and_scores_use_stable_id_not_argument_order() -> None:
    class MinimumRng:
        def randint(self, low: int, high: int) -> int:
            return low

    alice = _make_char("Alice", strength=20, constitution=90)
    bob = _make_char("Bob", strength=20, constitution=90)
    forward = resolve_combat(alice, bob, MinimumRng())
    reverse = resolve_combat(bob, alice, MinimumRng())

    assert forward.winner is reverse.winner is alice
    assert forward.log_entries == reverse.log_entries
    assert forward.end_reason == reverse.end_reason == "round_limit"


def test_final_states_account_for_actual_vitality_loss() -> None:
    mage = _make_mage("Mira")
    guard = _make_char("Guard", strength=45, constitution=50)
    result = resolve_combat(mage, guard, random.Random(2))

    for char in (mage, guard):
        state = result.state_for(char.char_id)
        assert state.damage_taken == state.starting_vitality - state.remaining_vitality
        assert state.damage_taken == sum(e.damage for e in result.log_entries if e.target_id == char.char_id)
        assert state.damage_dealt == sum(e.damage for e in result.log_entries if e.actor_id == char.char_id)


@pytest.mark.parametrize("invalid_id", ["", " ", "alice"])
def test_invalid_combat_ids_fail_before_consuming_randomness(invalid_id: str) -> None:
    alice = _make_char("Alice", strength=50, constitution=50)
    bob = _make_char("Bob", strength=50, constitution=50)
    bob.char_id = invalid_id
    rng = random.Random(42)
    before = rng.getstate()
    with pytest.raises(ValueError, match="distinct nonempty IDs"):
        resolve_combat(alice, bob, rng)
    assert rng.getstate() == before


def test_seeded_combat_does_not_depend_on_argument_order() -> None:
    alice = _make_char("Alice", strength=80, constitution=70)
    bob = _make_mage("Bob")
    assert resolve_combat(alice, bob, random.Random(42)) == resolve_combat(bob, alice, random.Random(42))


def test_battle_event_applies_loss_to_incapacitated_character_despite_higher_score() -> None:
    from fantasy_simulator.events import EventSystem
    from fantasy_simulator.world import World

    mage = Character(
        name="Mage", char_id="mage", age=25, gender="Female", race="Elf", job="Mage",
        strength=1, constitution=10, intelligence=100, dexterity=80, wisdom=80, charisma=20,
        skills={"Fireball": 20},
    )
    brute = Character(
        name="Brute", char_id="brute", age=25, gender="Male", race="Human", job="Warrior",
        strength=100, constitution=50, intelligence=10, dexterity=10, wisdom=10, charisma=20, skills={},
    )
    world = World()
    world.add_character(mage)
    world.add_character(brute)
    resolution = resolve_combat(mage, brute, random.Random(0))
    assert resolution.winner_power < resolution.loser_power  # The old score-only decision selected Brute.

    event = EventSystem().event_battle(mage, brute, world, rng=random.Random(0))

    params = event.metadata["render_params"]
    assert params["winner"] == mage.name
    assert params["loser"] == brute.name
    assert params["combat_log"][-1]["target_id"] == brute.char_id
    assert params["combat_log"][-1]["target_vitality"] == 0
    assert brute.injury_status == "injured"
    assert mage.injury_status == "none"
