"""
tests/test_world_memory.py - Unit tests for PR-F world memory features.

Covers: MemorialRecord, live traces, aliases, narrative context (epitaph/alias
variant selection), adventure_coordinator._apply_world_memory(), and
World serialization round-trips for all new fields.
"""

from __future__ import annotations

import random
from unittest.mock import MagicMock
from typing import Any

from fantasy_simulator.adventure import AdventureRun
from fantasy_simulator.character import Character
from fantasy_simulator.content.setting_bundle import default_aethoria_bundle
from fantasy_simulator.events import WorldEventRecord
from fantasy_simulator.narrative.context import (
    NarrativeContext,
    alias_for_event,
    build_narrative_context,
    derive_relation_hint,
    epitaph_for_character,
)
from fantasy_simulator.rumor import Rumor, RUMOR_MAX_AGE_MONTHS
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import MemorialRecord, World
from fantasy_simulator.simulation.adventure_coordinator import AdventureMixin


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_world() -> World:
    """Return a fresh world with the default Aethoria map."""
    return World()


def _first_loc_id(world: World) -> str:
    """Return the ID of the first location in grid order."""
    return next(iter(world._location_id_index))


def _make_char_stub(name: str = "Hero", job: str = "Warrior", char_id: str = "c1"):
    """Return a minimal Character-like object for narrative context tests."""
    return Character(name=name, age=30, gender="Male", race="Human", job=job, char_id=char_id)


# ---------------------------------------------------------------------------
# MemorialRecord dataclass
# ---------------------------------------------------------------------------

class TestMemorialRecord:
    def test_round_trip_serialization(self):
        rec = MemorialRecord(
            memorial_id="m1",
            character_id="c1",
            character_name="Aldric",
            location_id="loc_thornwood",
            year=1005,
            cause="adventure_death",
            epitaph="Here fell Aldric.",
        )
        data = rec.to_dict()
        restored = MemorialRecord.from_dict(data)
        assert restored.memorial_id == "m1"
        assert restored.character_id == "c1"
        assert restored.character_name == "Aldric"
        assert restored.location_id == "loc_thornwood"
        assert restored.year == 1005
        assert restored.cause == "adventure_death"
        assert restored.epitaph == "Here fell Aldric."

    def test_to_dict_contains_all_keys(self):
        rec = MemorialRecord("m2", "c2", "Lysara", "loc_millhaven", 1010, "battle_fatal", "In memory of Lysara.")
        d = rec.to_dict()
        for key in ("memorial_id", "character_id", "character_name", "location_id",
                    "year", "cause", "epitaph"):
            assert key in d, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# World.add_live_trace
# ---------------------------------------------------------------------------

class TestAddLiveTrace:
    def test_trace_added_to_location(self):
        world = _make_world()
        loc_id = "loc_aethoria_capital"
        world.add_live_trace(loc_id, 1001, "Aldric", "Aldric passed through Aethoria Capital (Year 1001).")
        loc = world.get_location_by_id(loc_id)
        assert len(loc.live_traces) == 1
        trace = loc.live_traces[0]
        assert trace["year"] == 1001
        assert trace["char_name"] == "Aldric"
        assert "Aldric" in trace["text"]

    def test_invalid_location_is_silently_ignored(self):
        world = _make_world()
        world.add_live_trace("loc_does_not_exist", 1000, "X", "text")
        # No exception

    def test_traces_trimmed_to_max(self):
        world = _make_world()
        loc_id = "loc_aethoria_capital"
        for i in range(World.MAX_LIVE_TRACES + 5):
            world.add_live_trace(loc_id, 1000 + i, f"char_{i}", f"text_{i}")
        loc = world.get_location_by_id(loc_id)
        assert len(loc.live_traces) == World.MAX_LIVE_TRACES
        # Most recent should be last
        assert loc.live_traces[-1]["char_name"] == f"char_{World.MAX_LIVE_TRACES + 4}"

    def test_traces_accumulate_across_multiple_characters(self):
        world = _make_world()
        loc_id = "loc_aethoria_capital"
        world.add_live_trace(loc_id, 1001, "A", "A text")
        world.add_live_trace(loc_id, 1002, "B", "B text")
        loc = world.get_location_by_id(loc_id)
        assert len(loc.live_traces) == 2


# ---------------------------------------------------------------------------
# World.add_memorial
# ---------------------------------------------------------------------------

class TestAddMemorial:
    def test_memorial_stored_in_world_dict(self):
        world = _make_world()
        world.add_memorial("m1", "c1", "Aldric", "loc_aethoria_capital", 1005,
                           "adventure_death", "Here fell Aldric.")
        assert "m1" in world.memorials
        rec = world.memorials["m1"]
        assert rec.character_name == "Aldric"

    def test_memorial_id_linked_to_location(self):
        world = _make_world()
        world.add_memorial("m1", "c1", "Aldric", "loc_aethoria_capital", 1005,
                           "adventure_death", "Here fell Aldric.")
        loc = world.get_location_by_id("loc_aethoria_capital")
        assert "m1" in loc.memorial_ids

    def test_duplicate_memorial_id_not_added_twice_to_location(self):
        world = _make_world()
        world.add_memorial("m1", "c1", "Aldric", "loc_aethoria_capital", 1005,
                           "adventure_death", "E1")
        world.add_memorial("m1", "c1", "Aldric", "loc_aethoria_capital", 1005,
                           "adventure_death", "E2")
        loc = world.get_location_by_id("loc_aethoria_capital")
        assert loc.memorial_ids.count("m1") == 1

    def test_invalid_location_still_stores_record(self):
        world = _make_world()
        world.add_memorial("m1", "c1", "X", "loc_nonexistent", 1000, "adventure_death", "E")
        assert "m1" in world.memorials
        # But no location linked (silently handled)


# ---------------------------------------------------------------------------
# World.add_alias
# ---------------------------------------------------------------------------

class TestAddAlias:
    def test_alias_appended_to_location(self):
        world = _make_world()
        world.add_alias("loc_aethoria_capital", "The Shining City")
        loc = world.get_location_by_id("loc_aethoria_capital")
        assert "The Shining City" in loc.aliases

    def test_alias_not_added_if_already_present(self):
        world = _make_world()
        world.add_alias("loc_aethoria_capital", "The Shining City")
        world.add_alias("loc_aethoria_capital", "The Shining City")
        loc = world.get_location_by_id("loc_aethoria_capital")
        assert loc.aliases.count("The Shining City") == 1

    def test_alias_capped_at_max(self):
        world = _make_world()
        for i in range(World.MAX_ALIASES + 3):
            world.add_alias("loc_aethoria_capital", f"Alias {i}")
        loc = world.get_location_by_id("loc_aethoria_capital")
        assert len(loc.aliases) == World.MAX_ALIASES

    def test_invalid_location_is_silently_ignored(self):
        world = _make_world()
        world.add_alias("loc_nonexistent", "Ghost Town")
        # No exception

    def test_different_aliases_all_added_within_cap(self):
        world = _make_world()
        world.add_alias("loc_aethoria_capital", "Alias A")
        world.add_alias("loc_aethoria_capital", "Alias B")
        world.add_alias("loc_aethoria_capital", "Alias C")
        loc = world.get_location_by_id("loc_aethoria_capital")
        assert "Alias A" in loc.aliases
        assert "Alias B" in loc.aliases
        assert "Alias C" in loc.aliases


# ---------------------------------------------------------------------------
# World.get_memorials_for_location
# ---------------------------------------------------------------------------

class TestGetMemorialsForLocation:
    def test_returns_records_for_known_location(self):
        world = _make_world()
        world.add_memorial("m1", "c1", "Aldric", "loc_aethoria_capital", 1005,
                           "adventure_death", "Epitaph 1")
        world.add_memorial("m2", "c2", "Lysara", "loc_aethoria_capital", 1006,
                           "battle_fatal", "Epitaph 2")
        results = world.get_memorials_for_location("loc_aethoria_capital")
        assert len(results) == 2
        names = {r.character_name for r in results}
        assert names == {"Aldric", "Lysara"}

    def test_returns_empty_for_location_with_no_memorials(self):
        world = _make_world()
        result = world.get_memorials_for_location("loc_aethoria_capital")
        assert result == []

    def test_returns_empty_for_unknown_location(self):
        world = _make_world()
        result = world.get_memorials_for_location("loc_nonexistent")
        assert result == []

    def test_stale_memorial_ids_are_skipped(self):
        """memorial_id in location but absent from world.memorials is skipped."""
        world = _make_world()
        loc = world.get_location_by_id("loc_aethoria_capital")
        loc.memorial_ids.append("m_stale")
        result = world.get_memorials_for_location("loc_aethoria_capital")
        assert result == []


# ---------------------------------------------------------------------------
# World serialization round-trip (memorials + live_traces)
# ---------------------------------------------------------------------------

class TestWorldMemoryRoundTrip:
    def test_setting_bundle_survives_to_dict_from_dict(self):
        world = _make_world()
        world.setting_bundle = default_aethoria_bundle(lore_text="Bundle lore for save/load.")
        world.setting_bundle.world_definition.era = "Second Dawn"

        data = world.to_dict()
        restored = World.from_dict(data)

        assert restored.setting_bundle.world_definition.lore_text == "Bundle lore for save/load."
        assert restored.setting_bundle.world_definition.era == "Second Dawn"
        assert restored.lore == "Bundle lore for save/load."

    def test_memorials_survive_to_dict_from_dict(self):
        world = _make_world()
        world.add_memorial("m1", "c1", "Aldric", "loc_aethoria_capital", 1005,
                           "adventure_death", "Epitaph for Aldric.")
        data = world.to_dict()
        assert "memorials" in data
        restored = World.from_dict(data)
        assert "m1" in restored.memorials
        assert restored.memorials["m1"].character_name == "Aldric"

    def test_live_traces_survive_to_dict_from_dict(self):
        world = _make_world()
        world.add_live_trace("loc_aethoria_capital", 1001, "Aldric",
                             "Aldric passed through (Year 1001).")
        data = world.to_dict()
        restored = World.from_dict(data)
        loc = restored.get_location_by_id("loc_aethoria_capital")
        assert len(loc.live_traces) == 1
        assert loc.live_traces[0]["char_name"] == "Aldric"

    def test_aliases_survive_to_dict_from_dict(self):
        world = _make_world()
        world.add_alias("loc_aethoria_capital", "The Crown City")
        data = world.to_dict()
        restored = World.from_dict(data)
        loc = restored.get_location_by_id("loc_aethoria_capital")
        assert "The Crown City" in loc.aliases

    def test_memorial_ids_linked_after_load(self):
        world = _make_world()
        world.add_memorial("m1", "c1", "Aldric", "loc_aethoria_capital", 1005,
                           "adventure_death", "Epitaph.")
        data = world.to_dict()
        restored = World.from_dict(data)
        loc = restored.get_location_by_id("loc_aethoria_capital")
        assert "m1" in loc.memorial_ids
        mems = restored.get_memorials_for_location("loc_aethoria_capital")
        assert len(mems) == 1

    def test_empty_world_has_empty_memorials(self):
        world = _make_world()
        data = world.to_dict()
        restored = World.from_dict(data)
        assert restored.memorials == {}


# ---------------------------------------------------------------------------
# narrative/context.py — epitaph_for_character
# ---------------------------------------------------------------------------

class TestEpitaphForCharacter:
    def test_warrior_job_uses_warrior_template(self):
        char = _make_char_stub(job="Warrior")
        result = epitaph_for_character("Aldric", 1005, "Thornwood", "adventure_death", char=char)
        # warrior template uses "warrior who met their end"
        assert "warrior" in result.lower()

    def test_paladin_job_uses_warrior_template(self):
        char = _make_char_stub(job="Paladin")
        result = epitaph_for_character("Aldric", 1005, "Thornwood", "adventure_death", char=char)
        assert "warrior" in result.lower()

    def test_mage_job_uses_mage_template(self):
        char = _make_char_stub(job="Mage")
        result = epitaph_for_character("Lysara", 1008, "Sunken Ruins", "adventure_death", char=char)
        assert "knowledge" in result.lower()

    def test_healer_job_uses_mage_template(self):
        char = _make_char_stub(job="Healer")
        result = epitaph_for_character("Mira", 1008, "Sunken Ruins", "adventure_death", char=char)
        assert "knowledge" in result.lower()

    def test_rogue_uses_adventurer_template(self):
        char = _make_char_stub(job="Rogue")
        result = epitaph_for_character("Shadow", 1010, "Dungeon", "adventure_death", char=char)
        # Rogue is neither combat nor magic → falls to adventurer
        assert "adventurer" in result.lower()

    def test_no_char_adventure_death_uses_adventurer_template(self):
        result = epitaph_for_character("Unknown", 1010, "Dungeon", "adventure_death", char=None)
        assert "adventurer" in result.lower()

    def test_no_char_other_cause_uses_default_template(self):
        result = epitaph_for_character("Unknown", 1010, "Dungeon", "battle", char=None)
        assert "memory" in result.lower()

    def test_char_name_year_location_in_output(self):
        char = _make_char_stub(job="Warrior")
        result = epitaph_for_character("Aldric", 1005, "Thornwood Forest", "adventure_death", char=char)
        assert "Aldric" in result
        assert "1005" in result
        assert "Thornwood Forest" in result

    def test_close_relation_context_uses_beloved_template(self):
        result = epitaph_for_character(
            "Aldric",
            1005,
            "Thornwood",
            "adventure_death",
            context=NarrativeContext(relation_tags=("spouse",)),
        )
        assert "loving memory" in result.lower()

    def test_relation_hint_uses_beloved_template_for_backward_compat(self):
        result = epitaph_for_character(
            "Aldric",
            1005,
            "Thornwood",
            "adventure_death",
            relation_hint="friend",
        )
        assert "whose loss was deeply felt" in result

    def test_rival_relation_context_uses_rival_template(self):
        result = epitaph_for_character(
            "Aldric",
            1005,
            "Thornwood",
            "adventure_death",
            context=NarrativeContext(relation_tags=("rival",)),
        )
        assert "rivals" in result.lower()

    def test_tragic_site_context_uses_tragic_year_template(self):
        result = epitaph_for_character(
            "Aldric",
            1005,
            "Thornwood",
            "battle",
            context=NarrativeContext(yearly_death_count=3),
        )
        assert "grievous year" in result.lower()

    def test_subject_rumor_heavy_context_uses_whispered_template(self):
        result = epitaph_for_character(
            "Aldric",
            1005,
            "Thornwood",
            "battle",
            context=NarrativeContext(subject_rumor_count=2),
        )
        assert "whispers" in result.lower()

    def test_unrelated_location_rumors_do_not_use_whispered_template(self):
        result = epitaph_for_character(
            "Aldric",
            1005,
            "Thornwood",
            "battle",
            context=NarrativeContext(location_rumor_count=3),
        )
        assert "whispers" not in result.lower()

    def test_relation_context_has_priority_over_subject_rumors(self):
        result = epitaph_for_character(
            "Aldric",
            1005,
            "Thornwood",
            "battle",
            context=NarrativeContext(relation_tags=("friend",), subject_rumor_count=2),
        )
        assert "deeply felt" in result.lower()
        assert "whispers" not in result.lower()


# ---------------------------------------------------------------------------
# narrative/context.py — alias_for_event
# ---------------------------------------------------------------------------

class TestAliasForEvent:
    def test_relation_hint_uses_rest_alias_for_death(self):
        result = alias_for_event("adventure_death", "Aldric", "Thornwood", relation_hint="spouse")
        assert "Rest" in result

    def test_relation_hint_uses_fall_alias_for_death(self):
        result = alias_for_event("adventure_death", "Aldric", "Thornwood", relation_hint="rival")
        assert "Fall" in result

    def test_adventure_death_returns_death_alias(self):
        result = alias_for_event("adventure_death", "Aldric", "Thornwood")
        assert "Aldric" in result
        # should reference "Demise" or similar from alias_death_site template

    def test_battle_fatal_returns_death_alias(self):
        result1 = alias_for_event("adventure_death", "Aldric", "Thornwood")
        result2 = alias_for_event("battle_fatal", "Aldric", "Thornwood")
        assert result1 == result2

    def test_death_returns_same_death_alias_family(self):
        result1 = alias_for_event("adventure_death", "Aldric", "Thornwood")
        result2 = alias_for_event("death", "Aldric", "Thornwood")
        assert result1 == result2

    def test_other_event_returns_notable_alias(self):
        result = alias_for_event("discovery", "Lysara", "Millhaven")
        assert "Lysara" in result

    def test_alias_does_not_include_location_name(self):
        """alias text is standalone — location param is not used in output."""
        result = alias_for_event("adventure_death", "Aldric", "Thornwood")
        # The alias key alias_death_site uses {name} only, not {location}
        assert "Thornwood" not in result

    def test_alias_uses_memorial_variant_when_location_has_prior_memorials(self):
        result = alias_for_event(
            "adventure_death",
            "Aldric",
            "Thornwood",
            context=NarrativeContext(location_memorial_count=2),
        )
        assert "memorial" in result.lower()

    def test_alias_uses_whisper_variant_when_subject_is_rumor_heavy(self):
        result = alias_for_event(
            "adventure_death",
            "Aldric",
            "Thornwood",
            context=NarrativeContext(subject_rumor_count=2),
        )
        assert "whisper" in result.lower()

    def test_alias_does_not_use_whisper_variant_for_unrelated_location_rumors(self):
        result = alias_for_event(
            "adventure_death",
            "Aldric",
            "Thornwood",
            context=NarrativeContext(location_rumor_count=3),
        )
        assert "whisper" not in result.lower()

    def test_alias_relation_priority_beats_subject_rumors(self):
        result = alias_for_event(
            "adventure_death",
            "Aldric",
            "Thornwood",
            context=NarrativeContext(relation_tags=("friend",), subject_rumor_count=2),
        )
        assert "rest" in result.lower()
        assert "whisper" not in result.lower()


class TestDeriveRelationHint:
    def test_returns_survivor_relation_toward_subject(self):
        observer = _make_char_stub(name="Leader", char_id="c_leader")
        observer.add_relation_tag("c_subject", "spouse")
        subject = _make_char_stub(name="Companion", char_id="c_subject")

        result = derive_relation_hint([observer], subject.char_id)

        assert result == "spouse"

    def test_ignores_subject_outbound_relations(self):
        observer = _make_char_stub(name="Leader", char_id="c_leader")
        subject = _make_char_stub(name="Companion", char_id="c_subject")
        subject.add_relation_tag(observer.char_id, "spouse")

        result = derive_relation_hint([observer], subject.char_id)

        assert result is None

    def test_legacy_single_character_mode_remains_available(self):
        char = _make_char_stub(name="Aldric", char_id="c_legacy")
        char.add_relation_tag("partner", "spouse")

        result = derive_relation_hint(char)

        assert result == "spouse"

    def test_legacy_single_character_mode_returns_none_without_relations(self):
        char = _make_char_stub(name="Aldric", char_id="c_legacy")

        result = derive_relation_hint(char)

        assert result is None


class TestBuildNarrativeContext:
    def test_collects_relation_tags_report_signal_and_world_memory(self):
        world = _make_world()
        world.year = 1010
        observer = _make_char_stub(name="Leader", job="Warrior", char_id="c_leader")
        subject = _make_char_stub(name="Companion", job="Mage", char_id="c_companion")
        observer.add_relation_tag(subject.char_id, "spouse")
        world.add_character(observer)
        world.add_character(subject)
        world.add_memorial("m1", subject.char_id, subject.name, "loc_thornwood", 1009, "adventure_death", "Epitaph")
        thornwood = world.get_location_by_id("loc_thornwood")
        thornwood.live_traces.extend([
            {"year": 1009, "char_name": "A", "text": "A"},
            {"year": 1009, "char_name": "B", "text": "B"},
        ])
        world.record_event(WorldEventRecord(
            record_id="d1",
            kind="death",
            year=1010,
            month=2,
            location_id="loc_thornwood",
            description="Death in Thornwood",
            severity=4,
        ))
        world.record_event(WorldEventRecord(
            record_id="d2",
            kind="death",
            year=1010,
            month=4,
            description="Another death",
            severity=5,
        ))

        context = build_narrative_context(
            world,
            "loc_thornwood",
            1010,
            observer=observer,
            subject_id=subject.char_id,
        )

        assert context.primary_relation_tag == "spouse"
        assert context.yearly_death_count == 2
        assert context.report_notable_count == 1
        assert context.location_memorial_count == 1
        assert context.location_trace_count == 2

    def test_collects_relation_tags_from_multiple_observers(self):
        world = _make_world()
        subject = _make_char_stub(name="Companion", char_id="c_subject")
        observer_a = _make_char_stub(name="Leader", char_id="c_leader")
        observer_b = _make_char_stub(name="Scout", char_id="c_scout")
        observer_a.add_relation_tag(subject.char_id, "friend")
        observer_b.add_relation_tag(subject.char_id, "spouse")
        world.add_character(observer_a)
        world.add_character(observer_b)
        world.add_character(subject)

        context = build_narrative_context(
            world,
            "loc_thornwood",
            1010,
            observer=[observer_a, observer_b],
            subject_id=subject.char_id,
        )

        assert context.primary_relation_tag == "spouse"
        assert set(context.relation_tags) == {"friend", "spouse"}

    def test_counts_fatal_event_kinds_in_yearly_death_signal(self):
        world = _make_world()
        observer = _make_char_stub(name="Leader", char_id="c_leader")
        subject = _make_char_stub(name="Companion", char_id="c_companion")
        observer.add_relation_tag(subject.char_id, "friend")
        world.add_character(observer)
        world.add_character(subject)
        world.record_event(WorldEventRecord(
            record_id="fatal_1",
            kind="adventure_death",
            year=1010,
            month=3,
            location_id="loc_thornwood",
            description="Adventure death",
            severity=5,
        ))
        world.record_event(WorldEventRecord(
            record_id="fatal_2",
            kind="battle_fatal",
            year=1010,
            month=7,
            location_id="loc_thornwood",
            description="Battle fatality",
            severity=5,
        ))

        context = build_narrative_context(
            world,
            "loc_thornwood",
            1010,
            observer=observer,
            subject_id=subject.char_id,
        )

        assert context.yearly_death_count == 2
        assert context.is_tragic_site is True

    def test_collects_location_and_subject_rumor_signals_separately(self):
        world = _make_world()
        observer = _make_char_stub(name="Leader", char_id="c_leader")
        subject = _make_char_stub(name="Companion", char_id="c_companion")
        observer.add_relation_tag(subject.char_id, "friend")
        world.add_character(observer)
        world.add_character(subject)
        world.rumors.extend([
            Rumor(source_location_id="loc_thornwood", target_subject=subject.char_id, age_in_months=0),
            Rumor(
                source_location_id="loc_thornwood",
                target_subject=subject.char_id,
                age_in_months=RUMOR_MAX_AGE_MONTHS - 1,
            ),
            Rumor(source_location_id="loc_thornwood", target_subject="c_other", age_in_months=0),
            Rumor(source_location_id="loc_thornwood", age_in_months=0),
            # Rumors at the exact max age are expired and are not counted.
            Rumor(
                source_location_id="loc_thornwood",
                target_subject=subject.char_id,
                age_in_months=RUMOR_MAX_AGE_MONTHS,
            ),
            Rumor(source_location_id="loc_millhaven", target_subject=subject.char_id, age_in_months=0),
        ])

        context = build_narrative_context(
            world,
            "loc_thornwood",
            1010,
            observer=observer,
            subject_id=subject.char_id,
        )

        assert context.location_rumor_count == 4
        assert context.subject_rumor_count == 2


# ---------------------------------------------------------------------------
# adventure_coordinator._apply_world_memory integration
# ---------------------------------------------------------------------------

class TestApplyWorldMemory:
    """Integration tests verifying _apply_world_memory is called correctly."""

    def _make_sim(self, seed: int = 42) -> Any:
        """Return a Simulator with a small seeded world."""
        world = World()
        for i in range(4):
            char = Character(
                name=f"Hero{i}",
                age=25 + i,
                gender="Male",
                race="Human",
                job="Warrior",
                char_id=f"c{i}",
            )
            char.location_id = "loc_aethoria_capital"
            world.add_character(char)
        return Simulator(world, seed=seed)

    def test_live_trace_created_after_adventure_completes(self):
        sim = self._make_sim(seed=10)
        # Run enough years that at least one adventure resolves
        for _ in range(25):
            sim.advance_years(1)
            total_traces = sum(
                len(loc.live_traces) for loc in sim.world.grid.values()
            )
            if total_traces > 0:
                break
        total_traces = sum(
            len(loc.live_traces) for loc in sim.world.grid.values()
        )
        assert total_traces > 0, "Expected at least one live trace after 25 years"

    def test_memorial_created_after_adventure_death(self):
        sim = self._make_sim(seed=77)
        for _ in range(60):
            sim.advance_years(1)
            if sim.world.memorials:
                break
        # If any character died on an adventure, there should be a memorial
        dead_adventure_chars = [
            run for run in sim.world.completed_adventures
            if run.outcome == "death"
        ]
        if dead_adventure_chars:
            assert sim.world.memorials, "Expected memorials for adventure deaths"

    def test_alias_created_for_location_after_death(self):
        sim = self._make_sim(seed=88)
        for _ in range(60):
            sim.advance_years(1)
            if any(loc.aliases for loc in sim.world.grid.values()):
                break
        # If any character died, there may be aliases
        dead_runs = [r for r in sim.world.completed_adventures if r.outcome == "death"]
        if dead_runs:
            any_alias = any(loc.aliases for loc in sim.world.grid.values())
            assert any_alias, "Expected at least one location alias after adventure deaths"

    def test_apply_world_memory_on_death_directly(self):
        """Test _apply_world_memory directly via a mock AdventureRun."""
        world = _make_world()
        world.year = 1010
        # Add a character
        char = Character(name="Aldric", age=30, gender="Male", race="Human",
                         job="Warrior", char_id="cA")
        char.location_id = "loc_aethoria_capital"
        world.add_character(char)

        # Build a mock AdventureRun with death outcome
        run = MagicMock(spec=AdventureRun)
        run.destination = "loc_thornwood"
        run.character_id = "cA"
        run.character_name = "Aldric"
        run.outcome = "death"
        run.year_started = 1008
        run.is_party = False
        run.member_ids = ["cA"]

        # Build a minimal mixin-like object
        class FakeMixin(AdventureMixin):
            def __init__(self_inner):
                self_inner.world = world
                self_inner.id_rng = random.Random(1)

        mixin = FakeMixin.__new__(FakeMixin)
        mixin.world = world
        mixin.id_rng = random.Random(1)

        mixin._apply_world_memory(run)

        # Live trace at destination
        dest = world.get_location_by_id("loc_thornwood")
        assert len(dest.live_traces) == 1
        # Memorial created
        assert len(world.memorials) == 1
        mem = next(iter(world.memorials.values()))
        assert mem.character_name == "Aldric"
        assert mem.cause == "adventure_death"
        # Alias generated
        assert len(dest.aliases) == 1

    def test_apply_world_memory_uses_deceased_member_for_memorial(self):
        """When a companion dies, memorial must reference companion, not leader."""
        world = _make_world()
        world.year = 1010
        leader = Character(name="Leader", age=30, gender="Male", race="Human", job="Warrior", char_id="cL")
        leader.location_id = "loc_aethoria_capital"
        companion = Character(name="Companion", age=28, gender="Female", race="Elf", job="Mage", char_id="cC")
        companion.location_id = "loc_aethoria_capital"
        companion.alive = False
        world.add_character(leader)
        world.add_character(companion)

        run = MagicMock(spec=AdventureRun)
        run.destination = "loc_thornwood"
        run.character_id = "cL"
        run.character_name = "Leader"
        run.death_member_id = "cC"
        run.outcome = "death"
        run.year_started = 1008
        run.is_party = True
        run.member_ids = ["cL", "cC"]

        mixin = object.__new__(AdventureMixin)
        mixin.world = world
        mixin.id_rng = random.Random(7)

        mixin._apply_world_memory(run)
        mem = next(iter(world.memorials.values()))
        assert mem.character_id == "cC"
        assert "Companion" in mem.character_name

    def test_apply_world_memory_uses_survivor_relation_for_epitaph(self):
        world = _make_world()
        world.year = 1010
        leader = Character(name="Leader", age=30, gender="Male", race="Human", job="Warrior", char_id="cL")
        companion = Character(name="Companion", age=28, gender="Female", race="Elf", job="Mage", char_id="cC")
        leader.add_relation_tag("cC", "spouse")
        leader.location_id = "loc_aethoria_capital"
        companion.location_id = "loc_aethoria_capital"
        companion.alive = False
        world.add_character(leader)
        world.add_character(companion)

        run = MagicMock(spec=AdventureRun)
        run.destination = "loc_thornwood"
        run.character_id = "cL"
        run.character_name = "Leader"
        run.death_member_id = "cC"
        run.outcome = "death"
        run.year_started = 1008
        run.is_party = True
        run.member_ids = ["cL", "cC"]

        mixin = object.__new__(AdventureMixin)
        mixin.world = world
        mixin.id_rng = random.Random(9)

        mixin._apply_world_memory(run)

        mem = next(iter(world.memorials.values()))
        assert "loving memory" in mem.epitaph.lower()
        dest = world.get_location_by_id("loc_thornwood")
        assert "Companion's Rest" in dest.aliases

    def test_apply_world_memory_solo_death_uses_job_based_epitaph(self):
        world = _make_world()
        world.year = 1010
        char = Character(name="Aldric", age=30, gender="Male", race="Human", job="Warrior", char_id="cA")
        char.location_id = "loc_aethoria_capital"
        char.add_relation_tag("partner", "spouse")
        world.add_character(char)

        run = MagicMock(spec=AdventureRun)
        run.destination = "loc_thornwood"
        run.character_id = "cA"
        run.character_name = "Aldric"
        run.outcome = "death"
        run.year_started = 1008
        run.is_party = False
        run.member_ids = ["cA"]
        run.death_member_id = None

        mixin = object.__new__(AdventureMixin)
        mixin.world = world
        mixin.id_rng = random.Random(11)

        mixin._apply_world_memory(run)

        memorial = next(iter(world.memorials.values()))
        assert "loving memory" not in memorial.epitaph.lower()
        assert "warrior" in memorial.epitaph.lower()
        dest = world.get_location_by_id("loc_thornwood")
        assert "Aldric's Rest" not in dest.aliases

    def test_apply_world_memory_current_death_does_not_trigger_whisper_variants(self):
        world = _make_world()
        world.year = 1010
        char = Character(name="Aldric", age=30, gender="Male", race="Human", job="Warrior", char_id="cA")
        char.location_id = "loc_aethoria_capital"
        world.add_character(char)

        run = MagicMock(spec=AdventureRun)
        run.destination = "loc_thornwood"
        run.character_id = "cA"
        run.character_name = "Aldric"
        run.outcome = "death"
        run.year_started = 1008
        run.is_party = False
        run.member_ids = ["cA"]
        run.death_member_id = None

        mixin = object.__new__(AdventureMixin)
        mixin.world = world
        mixin.id_rng = random.Random(12)

        mixin._apply_world_memory(run)

        memorial = next(iter(world.memorials.values()))
        dest = world.get_location_by_id("loc_thornwood")
        assert "whispers" not in memorial.epitaph.lower()
        assert all("whisper" not in alias.lower() for alias in dest.aliases)
        assert world.rumors == []

    def test_apply_world_memory_party_death_without_relations_uses_job_epitaph(self):
        world = _make_world()
        world.year = 1010
        leader = Character(name="Leader", age=30, gender="Male", race="Human", job="Warrior", char_id="cL")
        leader.location_id = "loc_aethoria_capital"
        companion = Character(name="Companion", age=28, gender="Female", race="Elf", job="Mage", char_id="cC")
        companion.location_id = "loc_aethoria_capital"
        companion.alive = False
        world.add_character(leader)
        world.add_character(companion)

        run = MagicMock(spec=AdventureRun)
        run.destination = "loc_thornwood"
        run.character_id = "cL"
        run.character_name = "Leader"
        run.death_member_id = "cC"
        run.outcome = "death"
        run.year_started = 1008
        run.is_party = True
        run.member_ids = ["cL", "cC"]

        mixin = object.__new__(AdventureMixin)
        mixin.world = world
        mixin.id_rng = random.Random(13)

        mixin._apply_world_memory(run)

        memorial = next(iter(world.memorials.values()))
        assert "loving memory" not in memorial.epitaph.lower()
        assert "knowledge" in memorial.epitaph.lower()

    def test_apply_world_memory_safe_return_no_memorial(self):
        """Safe return → live trace only, no memorial."""
        world = _make_world()
        world.year = 1010

        run = MagicMock(spec=AdventureRun)
        run.destination = "loc_thornwood"
        run.character_id = "cB"
        run.character_name = "Lysara"
        run.outcome = "safe_return"
        run.year_started = 1009
        run.is_party = False
        run.member_ids = ["cB"]

        mixin = object.__new__(AdventureMixin)
        mixin.world = world
        mixin.id_rng = random.Random(2)

        mixin._apply_world_memory(run)

        dest = world.get_location_by_id("loc_thornwood")
        assert len(dest.live_traces) == 1
        assert len(world.memorials) == 0
        assert len(dest.aliases) == 0

    def test_apply_world_memory_trace_text_reflects_outcome(self):
        """Trace text should differ between safe_return and retreat outcomes."""
        world = _make_world()
        world.year = 1010

        safe_run = MagicMock(spec=AdventureRun)
        safe_run.destination = "loc_thornwood"
        safe_run.character_id = "c_safe"
        safe_run.character_name = "Aldric"
        safe_run.outcome = "safe_return"
        safe_run.year_started = 1009
        safe_run.is_party = False
        safe_run.member_ids = ["c_safe"]

        retreat_run = MagicMock(spec=AdventureRun)
        retreat_run.destination = "loc_thornwood"
        retreat_run.character_id = "c_retreat"
        retreat_run.character_name = "Lysara"
        retreat_run.outcome = "retreat"
        retreat_run.year_started = 1009
        retreat_run.is_party = False
        retreat_run.member_ids = ["c_retreat"]

        mixin = object.__new__(AdventureMixin)
        mixin.world = world
        mixin.id_rng = random.Random(3)

        mixin._apply_world_memory(safe_run)
        mixin._apply_world_memory(retreat_run)

        dest = world.get_location_by_id("loc_thornwood")
        assert len(dest.live_traces) >= 2
        safe_text = dest.live_traces[-2]["text"].lower()
        retreat_text = dest.live_traces[-1]["text"].lower()
        assert safe_text != retreat_text
