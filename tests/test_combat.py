from __future__ import annotations

import random

from fantasy_simulator.character import Character
from fantasy_simulator.combat import resolve_combat


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


def test_resolve_combat_returns_standalone_resolution_without_mutating_combatants() -> None:
    alice = _make_char("Alice", strength=80, constitution=70)
    bob = _make_char("Bob", strength=20, constitution=30)
    original_stats = (alice.strength, alice.constitution, bob.strength, bob.constitution)

    resolution = resolve_combat(alice, bob, random.Random(0))

    assert resolution.winner is alice
    assert resolution.loser is bob
    assert (alice.strength, alice.constitution, bob.strength, bob.constitution) == original_stats
    assert len(resolution.log_entries) == 3
    assert resolution.log_entries[-1].outcome == "decisive"


def test_combat_log_payload_is_json_ready() -> None:
    alice = _make_char("Alice", strength=80, constitution=70)
    bob = _make_char("Bob", strength=20, constitution=30)

    payload = resolve_combat(alice, bob, random.Random(1)).combat_log_payload()

    assert payload[0]["round_number"] == 1
    assert payload[0]["actor_id"] == "alice"
    assert isinstance(payload[0]["attack_total"], int)
