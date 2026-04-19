"""TD-4 map-visible harness ownership and production-path guardrails."""

from __future__ import annotations

import pytest

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.ui.screens import render_world_map_views_for_location
from fantasy_simulator.world import World
from tests.harness_test_utils import build_seeded_world, content_lines


TARGET_LOCATION_ID = "loc_the_verdant_vale"


def _build_memory_heavy_world() -> World:
    world = World()
    world.add_alias(TARGET_LOCATION_ID, "The Lantern Vale")
    world.add_memorial(
        "mem_1",
        "char_1",
        "Aldric",
        TARGET_LOCATION_ID,
        1001,
        "death",
        "Here rests Aldric.",
    )
    world.add_live_trace(
        TARGET_LOCATION_ID,
        1002,
        "Lysara",
        "Lysara passed through at dawn",
    )
    world.record_event(
        WorldEventRecord(
            kind="death",
            year=1002,
            month=3,
            day=4,
            location_id=TARGET_LOCATION_ID,
            description="Aldric fell at The Verdant Vale",
        )
    )
    return world


def _map_visible_bundle_for_sim(sim: Simulator) -> dict[str, list[str]]:
    rendered = render_world_map_views_for_location(sim.world, TARGET_LOCATION_ID)
    return {
        "overview": content_lines(rendered["overview"]),
        "region": content_lines(rendered["region"]),
        "detail": content_lines(rendered["detail"]),
    }


def _memory_heavy_bundle_for_sim(sim: Simulator) -> dict[str, list[str]]:
    rendered = render_world_map_views_for_location(
        sim.world,
        TARGET_LOCATION_ID,
        include_overview=False,
    )
    return {
        "region": content_lines(rendered["region"]),
        "detail": content_lines(rendered["detail"]),
    }


def _capture_map_visible_bundle(locale: str) -> dict[str, list[str]]:
    set_locale(locale)
    sim = Simulator(build_seeded_world(7), events_per_year=4, adventure_steps_per_year=2, seed=99)
    sim.advance_months(24)
    return _map_visible_bundle_for_sim(sim)


def _capture_memory_heavy_bundle(locale: str) -> dict[str, list[str]]:
    set_locale(locale)
    sim = Simulator(_build_memory_heavy_world(), events_per_year=0, adventure_steps_per_year=0, seed=99)
    return _memory_heavy_bundle_for_sim(sim)


@pytest.fixture(autouse=True)
def _restore_locale():
    previous = get_locale()
    yield
    set_locale(previous)


def _assert_seeded_map_visible_bundle(bundle: dict[str, list[str]]) -> None:
    assert bundle["overview"][0] == "  === WORLD OVERVIEW: Aethoria (Year: 1002) ==="
    assert any("The Verdant Vale - village" in line for line in bundle["overview"])
    assert any("Aethoria Capital - city" in line for line in bundle["overview"])

    assert bundle["region"][:5] == [
        "  === REGION MAP: The Verdant Vale ===",
        "      01234",
        "    2|EMASS|",
        "    3|DDHMD|",
        "    4|SS@OC|",
    ]
    assert "  Landmarks & World Memory:" in bundle["region"]
    assert any("Native name: Branthethal" in line for line in bundle["region"])
    assert any("Native name: Branthethal" in line for line in bundle["region"])

    assert bundle["detail"][:10] == [
        "  | V The Verdant Vale (village)                     |",
        "  | Terrain: plains (,)                              |",
        "  | Elev:128 Moist:128 Temp:128                      |",
        "  | Safety: tense                                    |",
        "  | Danger:  68 (high)                               |",
        "  | Traffic: ++ (medium)                             |",
        "  | Pop: 0                                           |",
        "  | Prosperity: stable (50)                          |",
        "  | Mood: calm (51)                                  |",
        "  | Rumor heat: 20 (low)                             |",
    ]
    assert "  | Native name: Branthethal                         |" in bundle["detail"]
    assert "  | Markers: Has alias                               |" not in bundle["detail"]


def _assert_memory_heavy_bundle(bundle: dict[str, list[str]]) -> None:
    assert "    - Memorial: The Verdant Vale holds a lasting memorial" in bundle["region"]
    assert "      Native name: Branthethal" in bundle["region"]
    assert "      Also known as: The Lantern Vale" in bundle["region"]
    assert "      Memorial: [Year 1001] Here rests Aldric." in bundle["region"]
    assert "      Recent: Lysara passed through at dawn" in bundle["region"]

    assert bundle["detail"][:10] == [
        "  | V The Verdant Vale (village)                     |",
        "  | Terrain: plains (,)                              |",
        "  | Elev:128 Moist:128 Temp:128                      |",
        "  | Safety: tense                                    |",
        "  | Danger:  30 (low)                                |",
        "  | Traffic: + (medium)                              |",
        "  | Pop: 0                                           |",
        "  | Prosperity: stable (50)                          |",
        "  | Mood: calm (55)                                  |",
        "  | Rumor heat: 20 (low)                             |",
    ]
    assert "  | Markers: Memorial present, Has alias, Recent d...|" in bundle["detail"]
    assert "  | Native name: Branthethal                         |" in bundle["detail"]
    assert "  | Known as: The Lantern Vale                       |" in bundle["detail"]
    assert "  |   [Year 1001] Here rests Aldric.                 |" in bundle["detail"]
    assert "  |   - Lysara passed through at dawn                |" in bundle["detail"]


def test_seeded_map_visible_bundle_matches_expected_contract() -> None:
    _assert_seeded_map_visible_bundle(_capture_map_visible_bundle("en"))


def test_memory_heavy_bundle_matches_expected_contract() -> None:
    _assert_memory_heavy_bundle(_capture_memory_heavy_bundle("en"))


def test_midyear_save_load_preserves_map_visible_bundle(tmp_path) -> None:
    set_locale("en")
    sim = Simulator(build_seeded_world(7), events_per_year=4, adventure_steps_per_year=2, seed=99)
    sim.advance_months(30)
    save_path = tmp_path / "midyear-map-visible.json"
    remaining_months = 18

    assert save_simulation(sim, str(save_path)) is True

    restored = load_simulation(str(save_path))

    assert restored is not None

    sim.advance_months(remaining_months)
    restored.advance_months(remaining_months)

    assert _map_visible_bundle_for_sim(restored) == _map_visible_bundle_for_sim(sim)


def test_save_load_preserves_memory_heavy_bundle_through_world_map_flow(tmp_path) -> None:
    set_locale("en")
    sim = Simulator(_build_memory_heavy_world(), events_per_year=0, adventure_steps_per_year=0, seed=99)
    save_path = tmp_path / "memory-heavy-world-map-flow.json"

    assert save_simulation(sim, str(save_path)) is True

    restored = load_simulation(str(save_path))

    assert restored is not None
    assert _memory_heavy_bundle_for_sim(restored) == _memory_heavy_bundle_for_sim(sim)
