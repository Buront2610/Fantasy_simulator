"""Inspection-oriented query regression tests."""

from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.rumor import Rumor
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World


def test_get_active_rumors_can_filter_to_one_location():
    world = World()
    world.rumors.extend(
        [
            Rumor(
                id="rumor_capital",
                description="Capital rumor",
                reliability="plausible",
                source_location_id="loc_aethoria_capital",
            ),
            Rumor(
                id="rumor_forest",
                description="Forest rumor",
                reliability="certain",
                source_location_id="loc_thornwood",
            ),
        ]
    )
    sim = Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=7)

    lines = sim.get_active_rumors(location_id="loc_thornwood")

    assert lines == ["Forest rumor (certain)"]


def test_get_location_observation_surfaces_recent_events_and_rumors():
    world = World()
    world.record_event(
        WorldEventRecord(
            record_id="obs_1",
            kind="meeting",
            year=world.year,
            month=3,
            location_id="loc_aethoria_capital",
            description="Delegates gathered at the capital.",
            severity=2,
        )
    )
    world.rumors.append(
        Rumor(
            id="rumor_capital",
            description="People whisper about the delegates.",
            reliability="plausible",
            source_location_id="loc_aethoria_capital",
        )
    )
    sim = Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=7)

    observation = sim.get_location_observation("loc_aethoria_capital")

    assert "Recent events" in observation
    assert "Delegates gathered at the capital." in observation
    assert "Rumors & Intelligence" in observation
    assert "People whisper about the delegates." in observation
