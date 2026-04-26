"""Region-aware character-creator tests for bundle authoring semantics."""

from __future__ import annotations

import random

from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.content.setting_bundle import default_aethoria_bundle


def test_character_creator_exposes_location_entries_for_bundle_authoring():
    creator = CharacterCreator(setting_bundle=default_aethoria_bundle())

    location_entries = creator.location_entries

    assert any(location_id == "loc_aethoria_capital" for location_id, *_rest in location_entries)
    capital_entry = next(entry for entry in location_entries if entry[0] == "loc_aethoria_capital")
    assert capital_entry[1] == "Aethoria Capital"
    assert "capital" in capital_entry[3]


def test_create_random_prefers_region_authored_race_pool_when_available():
    creator = CharacterCreator(setting_bundle=default_aethoria_bundle())

    races = {
        creator.create_random(region="loc_thornwood", rng=random.Random(seed)).race
        for seed in range(5)
    }

    assert races == {"Elf"}
