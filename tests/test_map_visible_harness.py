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


EXPECTED_MAP_VISIBLE_BUNDLE_EN = {
    "overview": [
        "  === WORLD OVERVIEW: Aethoria (Year: 1002) ===",
        "    01234",
        "  0|!!!!!|",
        "  1|!!!!!|",
        "  2|!!!!!|",
        "  3|!!!!$|",
        "  4|SS!!$|",
        "  Sites:",
        "    (0,0) Frostpeak Summit - mountain [!]",
        "    (1,0) The Grey Pass - mountain [!] pop:1",
        "    (2,0) Skyveil Monastery - village [!]",
        "    (3,0) Ironvein Mine - dungeon [!]",
        "    (4,0) Stormwatch Keep - mountain [!]",
        "    (0,1) Thornwood - forest [!]",
        "    (1,1) Ashenvale - forest [!]",
        "    (2,1) Silverbrook - city [!$]",
        "    (3,1) Goblin Warrens - dungeon [!]",
        "    (4,1) Eastwatch Tower - village [!]",
        "    (0,2) Elderroot Forest - forest [!]",
        "    (1,2) Millhaven - village [!]",
        "    (2,2) Aethoria Capital - city [!$]",
        "    (3,2) Sunken Ruins - dungeon [!]",
        "    (4,2) Saltmarsh - village [!]",
        "    (0,3) Dragonbone Ridge - mountain [!]",
        "    (1,3) Dusty Crossroads - plains [!] pop:1",
        "    (2,3) Hearthglow Town - city [!$]",
        "    (3,3) Mirefen Swamp - dungeon [!]",
        "    (4,3) Dawnport - city [$]",
        "    (0,4) Sunbaked Plains - plains pop:1",
        "    (1,4) Sandstone Outpost - village pop:2",
        "    (2,4) The Verdant Vale - village [!]",
        "    (3,4) Obsidian Crater - dungeon [!] pop:1",
        "    (4,4) Coral Cove - city [$]",
        "  Routes:",
        "    Frostpeak Summit <-> The Grey Pass (Mountain Pass)",
        "    Frostpeak Summit <-> Thornwood (Mountain Pass)",
        "    The Grey Pass <-> Skyveil Monastery (Mountain Pass)",
        "    The Grey Pass <-> Ashenvale (Mountain Pass)",
        "    Skyveil Monastery <-> Ironvein Mine (Road)",
        "    Skyveil Monastery <-> Silverbrook (Road)",
        "    Ironvein Mine <-> Stormwatch Keep (Mountain Pass)",
        "    Ironvein Mine <-> Goblin Warrens (Road)",
        "    Stormwatch Keep <-> Eastwatch Tower (Mountain Pass)",
        "    Thornwood <-> Ashenvale (Road)",
        "    Thornwood <-> Elderroot Forest (Road)",
        "    Ashenvale <-> Silverbrook (Road)",
        "    Ashenvale <-> Millhaven (Road)",
        "    Silverbrook <-> Goblin Warrens (Road)",
        "    Silverbrook <-> Aethoria Capital (Road)",
        "    Goblin Warrens <-> Eastwatch Tower (Road)",
        "    Goblin Warrens <-> Sunken Ruins (Road)",
        "    Eastwatch Tower <-> Saltmarsh (Road)",
        "    Elderroot Forest <-> Millhaven (Road)",
        "    Elderroot Forest <-> Dragonbone Ridge (Mountain Pass)",
        "    Millhaven <-> Aethoria Capital (Road)",
        "    Millhaven <-> Dusty Crossroads (Road)",
        "    Aethoria Capital <-> Sunken Ruins (Road)",
        "    Aethoria Capital <-> Hearthglow Town (Road)",
        "    Sunken Ruins <-> Saltmarsh (Road)",
        "    Sunken Ruins <-> Mirefen Swamp (Road)",
        "    Saltmarsh <-> Dawnport (Road)",
        "    Dragonbone Ridge <-> Dusty Crossroads (Mountain Pass)",
        "    Dragonbone Ridge <-> Sunbaked Plains (Mountain Pass)",
        "    Dusty Crossroads <-> Hearthglow Town (Road)",
        "    Dusty Crossroads <-> Sandstone Outpost (Road)",
        "    Hearthglow Town <-> Mirefen Swamp (Road)",
        "    Hearthglow Town <-> The Verdant Vale (Road)",
        "    Mirefen Swamp <-> Dawnport (Road)",
        "    Mirefen Swamp <-> Obsidian Crater (Road)",
        "    Dawnport <-> Coral Cove (Road)",
        "    Sunbaked Plains <-> Sandstone Outpost (Road)",
        "    Sandstone Outpost <-> The Verdant Vale (Road)",
        "    The Verdant Vale <-> Obsidian Crater (Road)",
        "    Obsidian Crater <-> Coral Cove (Road)",
        "  Legend:",
        "    Terrain glyphs:",
        "      ~ = Ocean",
        "      . = Coast",
        "      , = plains",
        "      T = forest",
        "      n = Hills",
        "      ^ = mountain",
        "      % = Swamp",
        "      : = Desert",
        "      * = Tundra",
        "      = = River",
        "    Overlay markers:",
        "      ! = High danger",
        "      $ = High traffic",
        "      ? = High rumor heat",
        "      m = Memorial present",
        "      a = Has alias",
        "      + = Recent death site",
        "      * = Highlighted / selected",
    ],
    "region": [
        "  === REGION MAP: The Verdant Vale ===",
        "      01234",
        "    2|EMASS|",
        "    3|DDHMD|",
        "    4|SS@OC|",
        "  What stands out here:",
        "    - Route: Hearthglow Town via Road",
        "    - Danger: Obsidian Crater is a high-risk site",
        "  Nearby sites:",
        "         Elderroot Forest (forest) D:! T:  R:  [!]",
        "         Millhaven (village) D:! T:o R:  [!]",
        "         Aethoria Capital (city) D:! T:O R:~ [!$]",
        "         Sunken Ruins (dungeon) D:! T:  R:~ [!]",
        "         Saltmarsh (village) D:! T:o R:  [!]",
        "         Dragonbone Ridge (mountain) D:! T:  R:  [!]",
        "         Dusty Crossroads (plains) D:! T:o R:  [!]",
        "     <-> Hearthglow Town (city) D:! T:O R:~ [!$]",
        "         Mirefen Swamp (dungeon) D:! T:  R:~ [!]",
        "         Dawnport (city) D:. T:O R:~ [$]",
        "         Sunbaked Plains (plains) D:. T:o R: ",
        "     <-> Sandstone Outpost (village) D:. T:o R: ",
        "   @     The Verdant Vale (village) D:! T:o R:  [!]",
        "     <-> Obsidian Crater (dungeon) D:! T:  R:~ [!]",
        "         Coral Cove (city) D:. T:O R:~ [$]",
        "  Routes from here:",
        "    Hearthglow Town <-> The Verdant Vale (Road)",
        "    Sandstone Outpost <-> The Verdant Vale (Road)",
        "    The Verdant Vale <-> Obsidian Crater (Road)",
    ],
    "detail": [
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
    ],
}


EXPECTED_MEMORY_HEAVY_BUNDLE_EN = {
    "region": [
        "  === REGION MAP: The Verdant Vale ===",
        "      01234",
        "    2|EMASS|",
        "    3|DDHMD|",
        "    4|SS@OC|",
        "  What stands out here:",
        "    - Route: Hearthglow Town via Road",
        "    - Danger: Obsidian Crater is a high-risk site",
        "    - Memorial: The Verdant Vale holds a lasting memorial",
        "  Nearby sites:",
        "         Elderroot Forest (forest) D:. T:  R: ",
        "         Millhaven (village) D:  T:o R: ",
        "         Aethoria Capital (city) D:  T:O R:~ [$]",
        "         Sunken Ruins (dungeon) D:! T:  R:~ [!]",
        "         Saltmarsh (village) D:  T:o R: ",
        "         Dragonbone Ridge (mountain) D:. T:  R: ",
        "         Dusty Crossroads (plains) D:. T:  R: ",
        "     <-> Hearthglow Town (city) D:  T:O R:~ [$]",
        "         Mirefen Swamp (dungeon) D:! T:  R:~ [!]",
        "         Dawnport (city) D:  T:O R:~ [$]",
        "         Sunbaked Plains (plains) D:. T:  R: ",
        "     <-> Sandstone Outpost (village) D:  T:o R: ",
        "   @     The Verdant Vale (village) D:  T:o R:  [ma+]",
        "     <-> Obsidian Crater (dungeon) D:! T:  R:~ [!]",
        "         Coral Cove (city) D:  T:O R:~ [$]",
        "  Routes from here:",
        "    Hearthglow Town <-> The Verdant Vale (Road)",
        "    Sandstone Outpost <-> The Verdant Vale (Road)",
        "    The Verdant Vale <-> Obsidian Crater (Road)",
        "  Landmarks & World Memory:",
        "    The Verdant Vale:",
        "      Also known as: The Lantern Vale",
        "      Memorial: [Year 1001] Here rests Aldric.",
        "      Recent: Lysara passed through at dawn",
    ],
    "detail": [
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
        "  | Markers: Memorial present, Has alias, Recent d...|",
        "  | Known as: The Lantern Vale                       |",
        "  | Memorials:                                       |",
        "  |   [Year 1001] Here rests Aldric.                 |",
        "  | Recent visitors:                                 |",
        "  |   - Lysara passed through at dawn                |",
    ],
}


def test_seeded_map_visible_bundle_matches_expected_english_snapshot() -> None:
    assert _capture_map_visible_bundle("en") == EXPECTED_MAP_VISIBLE_BUNDLE_EN


def test_memory_heavy_bundle_matches_expected_english_snapshot() -> None:
    assert _capture_memory_heavy_bundle("en") == EXPECTED_MEMORY_HEAVY_BUNDLE_EN


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
