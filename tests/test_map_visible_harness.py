"""TD-4 map-visible harness ownership and production-path guardrails."""

from __future__ import annotations

import pytest

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.ui.ui_helpers import display_width
from fantasy_simulator.ui.map_view_models import build_map_info
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


def _capture_rendered_map_views(locale: str) -> dict[str, str]:
    set_locale(locale)
    sim = Simulator(build_seeded_world(7), events_per_year=4, adventure_steps_per_year=2, seed=99)
    sim.advance_months(24)
    return render_world_map_views_for_location(sim.world, TARGET_LOCATION_ID)


def _boxed_detail_widths(detail: str) -> set[int]:
    return {
        display_width(line)
        for line in detail.splitlines()
        if line.startswith("  |") or line.startswith("  +")
    }


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
    assert bundle["region"][5:25] == [
        "  Region detail:",
        "    |TTTTT,,,,, ### nn/nn,,,,,|",
        "    |TToTT,,o,, #C# nnDnn,,o,,|",
        "    |TTTTT,,,,, #=# nn\\nn,,,,,|",
        "    |^^^^^,,,,, ### nn/nn ### |",
        "    |^^o^^,,o,, #C# nnDnn #C# |",
        "    |^^^^^,,,,, #=# nn\\nn #=# |",
        "    |,,,,,,,,,,,,,,,nn/nn ### |",
        "    |,,o,,,,o,,,,@,,nnDnn #C# |",
        "    |,,,,,,,,,,,,,,,nn\\nn #=# |",
        "  Route sketch:",
        "    |            ###            |",
        "    | o-----o----#C#----D-----o |",
        "    | ^     |    #=#    |     | |",
        "    | ^     |    ###    |    ###|",
        "    | o^^^^^o----#C#----D----#C#|",
        "    | ^     |    #=#    |    #=#|",
        "    | ^     |     |     |    ###|",
        "    | o-----o-----@-----D----#C#|",
        "    |                        #=#|",
    ]
    assert "  Landmarks & World Memory:" in bundle["region"]
    assert any("Native name: Branthethal" in line for line in bundle["region"])
    assert any("Native name: Branthethal" in line for line in bundle["region"])

    assert bundle["detail"][:30] == [
        "  | V The Verdant Vale (village)                     |",
        "  | Local site sketch                                |",
        "  |         _       _          B                     |",
        "  |    ____/ \\__ __/ \\____    []                     |",
        "  |   | []  []  |  []  [] |                          |",
        "  |   |   o     |   ..    |====                      |",
        "  |   |____   __|__   ____|                          |",
        "  |        |_|     |_|                               |",
        "  | Local route sketch                               |",
        "  |  +-------------------------------+               |",
        "  |  |                               |               |",
        "  |  |           C                   |               |",
        "  |  |            \\             /--D |               |",
        "  |  |             -\\    /------     |               |",
        "  |  |            ---@---            |               |",
        "  |  |     ------/                   |               |",
        "  |  | o--/                          |               |",
        "  |  |                               |               |",
        "  |  |                               |               |",
        "  |  +-------------------------------+               |",
        "  | Sketch cues: !=High danger                       |",
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
    assert "    The Verdant Vale: Memory: Memorial, Trace" in bundle["region"]

    assert bundle["detail"][:31] == [
        "  | V The Verdant Vale (village)                     |",
        "  | Local site sketch                                |",
        "  |         _       _          B                     |",
        "  |    ____/ \\__ __/ \\____    []                     |",
        "  |   | []  []  |  []  [] |                          |",
        "  |   |   o     |   ..    |====                      |",
        "  |   |____   __|__   ____|                          |",
        "  |        |_|     |_|                               |",
        "  | Local route sketch                               |",
        "  |  +-------------------------------+               |",
        "  |  |                               |               |",
        "  |  |           C                   |               |",
        "  |  |            \\             /--D |               |",
        "  |  |             -\\    /------     |               |",
        "  |  |            ---@---            |               |",
        "  |  |     ------/                   |               |",
        "  |  | o--/                          |               |",
        "  |  |                               |               |",
        "  |  |                               |               |",
        "  |  +-------------------------------+               |",
        "  | Sketch cues: M=Memorial                          |",
        "  | Terrain: plains (,)                              |",
        "  | Elev:128 Moist:128 Temp:128                      |",
        "  | Safety: tense                                    |",
        "  | Danger:  30 (low)                                |",
        "  | Traffic: + (medium)                              |",
        "  | Pop: 0                                           |",
        "  | Local cues: Memory: Memorial, Trace              |",
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


@pytest.mark.parametrize("locale", ["en", "ja"])
def test_map_views_keep_display_width_budgets_across_locales(locale: str) -> None:
    rendered = _capture_rendered_map_views(locale)

    assert {name: max(display_width(line) for line in text.splitlines()) for name, text in rendered.items()} == {
        "region": 58 if locale == "en" else 57,
        "detail": 54,
        "overview": 57 if locale == "en" else 49,
    }
    assert _boxed_detail_widths(rendered["detail"]) == {54}


def test_map_views_surface_current_location_control() -> None:
    set_locale("en")
    rendered = render_world_map_views_for_location(
        World(),
        "loc_aethoria_capital",
        include_overview=False,
    )

    assert "    - Control: Aethoria Capital is held by Aethorian Crown Council" in rendered["region"]
    assert "  | Control: Aethorian Crown Council                 |" in rendered["detail"]


def test_map_views_surface_authored_local_cues() -> None:
    set_locale("en")
    rendered = render_world_map_views_for_location(
        World(),
        "loc_aethoria_capital",
        include_overview=False,
    )

    assert "  Local cues:" in rendered["region"]
    assert "    The Grey Pass: Site: Gate" in rendered["region"]
    assert "    Silverbrook: Site: Market; Terrain: River" in rendered["region"]
    assert "    Aethoria Capital: Site: Gate, Market, Notice board" in rendered["region"]
    assert "    Sunken Ruins: Memory: Accident site" in rendered["region"]
    assert "  | Local cues: Site: Gate, Market, Notice board     |" in rendered["detail"]


def test_location_detail_uses_larger_city_site_sketch() -> None:
    set_locale("en")
    rendered = render_world_map_views_for_location(
        World(),
        "loc_aethoria_capital",
        include_overview=False,
    )

    detail = rendered["detail"]
    assert "  | Local site sketch                                |" in detail
    assert "  |        ____||____        ________                |" in detail
    assert "  |   ____/ []  []  \\______/ [] []  \\____            |" in detail
    assert "  |        |  G |===== main road =====| G |          |" in detail
    assert "  |        /      market square       \\              |" in detail
    assert "  | Local route sketch                               |" in detail
    assert "  |  |            \\             /--D |               |" in detail
    assert "  |  |            ---@---            |               |" in detail
    assert "  | Sketch cues: G=Gate / $=Market / B=Notice board  |" in detail


def test_region_route_sketch_renders_cities_as_blocks() -> None:
    set_locale("en")
    rendered = render_world_map_views_for_location(
        World(),
        "loc_the_verdant_vale",
        include_overview=False,
    )

    route_sketch = rendered["region"].split("  What stands out here:", maxsplit=1)[0]
    assert "    | o-----o----#C#----D-----o |" in route_sketch
    assert "    | o^^^^^o----#C#----D----#C#|" in route_sketch
    assert "    | o-----o-----@-----D----#C#|" in route_sketch
    assert "o---o---C---D---C" not in route_sketch


def test_region_detail_grid_renders_terrain_and_city_blocks() -> None:
    set_locale("en")
    rendered = render_world_map_views_for_location(
        World(),
        "loc_the_verdant_vale",
        include_overview=False,
    )

    region_detail = rendered["region"].split("  Route sketch:", maxsplit=1)[0]
    assert "  Region detail:" in region_detail
    assert "    |TTTTT,,,,, ### nn/nn,,,,,|" in region_detail
    assert "    |TToTT,,o,, #C# nnDnn,,o,,|" in region_detail
    assert "    |,,o,,,,o,,,,@,,nnDnn #C# |" in region_detail
    assert "    4|SS@OC|" in region_detail


def test_location_detail_surfaces_name_etymology_preview() -> None:
    set_locale("en")
    rendered = render_world_map_views_for_location(
        World(),
        "loc_thornwood",
        include_overview=False,
    )

    assert "  | Native name: Thelbryn                            |" in rendered["detail"]
    assert "  | Name origin: Thelbryn < Sindral; authored nati...|" in rendered["detail"]


def test_map_views_surface_runtime_local_cues() -> None:
    set_locale("en")
    world = World()
    route = next(
        route for route in world.routes
        if route.from_site_id == "loc_aethoria_capital" or route.to_site_id == "loc_aethoria_capital"
    )
    world.apply_route_blocked_change(route.route_id, True, month=2, day=3)
    world.add_memorial(
        "mem_runtime",
        "char_1",
        "Aldric",
        "loc_aethoria_capital",
        world.year,
        "death",
        "Here rests Aldric.",
    )
    world.add_live_trace(
        "loc_aethoria_capital",
        world.year,
        "Lysara",
        "Lysara passed through at dawn",
    )

    rendered = render_world_map_views_for_location(
        world,
        "loc_aethoria_capital",
        include_overview=False,
    )

    assert (
        "    Aethoria Capital: Site: Gate, Market, Notice board; Memory: Memorial, Trace; "
        "Route: Blocked route"
        in rendered["region"]
    )
    assert "  | Local cues: Site: Gate, Market, Notice board; ...|" in rendered["detail"]


def test_map_view_model_structures_local_cues_for_filtering() -> None:
    set_locale("en")
    world = World()
    route = next(
        route for route in world.routes
        if route.from_site_id == "loc_aethoria_capital" or route.to_site_id == "loc_aethoria_capital"
    )
    world.apply_route_blocked_change(route.route_id, True, month=2, day=3)
    world.add_memorial(
        "mem_runtime",
        "char_1",
        "Aldric",
        "loc_aethoria_capital",
        world.year,
        "death",
        "Here rests Aldric.",
    )

    info = build_map_info(world, "loc_aethoria_capital")
    capital = next(cell for cell in info.cells.values() if cell.location_id == "loc_aethoria_capital")

    assert [
        (cue.category, cue.tag, cue.label, cue.priority)
        for cue in capital.local_feature_cues
    ] == [
        ("site", "gate", "Gate", 10),
        ("site", "market", "Market", 20),
        ("site", "notice_board", "Notice board", 30),
        ("memory", "memorial", "Memorial", 60),
        ("memory", "trace", "Trace", 70),
        ("route", "blocked_route", "Blocked route", 80),
    ]


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
