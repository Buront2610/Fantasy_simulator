from __future__ import annotations

import io
from contextlib import redirect_stdout

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.i18n import set_locale
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.reports import generate_monthly_report
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.terrain import RouteEdge, Site, TerrainCell, TerrainMap
from fantasy_simulator.ui.render_backend import PrintRenderBackend
from fantasy_simulator.ui.screens import _show_location_history
from fantasy_simulator.ui.ui_context import UIContext
from fantasy_simulator.world import LocationState, World


class _PickThirdInput:
    def __init__(self) -> None:
        self.calls = 0

    def read_line(self, prompt: str = "") -> str:
        self.calls += 1
        return "3" if self.calls == 1 else ""

    def read_menu_key(self, pairs, default=None):
        return pairs[0][0]

    def pause(self, message: str = "") -> None:
        return None


def _make_location(world: World, *, loc_id: str, name: str, x: int) -> LocationState:
    defaults = world.location_state_defaults(loc_id, "village")
    return LocationState(
        id=loc_id,
        canonical_name=name,
        description=f"{name} description",
        region_type="village",
        x=x,
        y=0,
        **defaults,
    )


def _build_sparse_route_world() -> World:
    world = World(name="Custom", width=3, height=1, _skip_defaults=True)
    for x, (loc_id, name) in enumerate(
        [("loc_alpha", "Alpha"), ("loc_bravo", "Bravo"), ("loc_charlie", "Charlie")]
    ):
        world._register_location(_make_location(world, loc_id=loc_id, name=name, x=x))

    terrain = TerrainMap(width=3, height=1)
    for x in range(3):
        terrain.set_cell(TerrainCell(x=x, y=0, biome="plains"))
    world.terrain_map = terrain
    world.sites = [
        Site(location_id="loc_alpha", x=0, y=0, site_type="village"),
        Site(location_id="loc_bravo", x=1, y=0, site_type="village"),
        Site(location_id="loc_charlie", x=2, y=0, site_type="village"),
    ]
    world.routes = [
        RouteEdge("route_alpha_bravo", "loc_alpha", "loc_bravo", "road"),
        RouteEdge("route_bravo_charlie", "loc_bravo", "loc_charlie", "road", blocked=True),
    ]
    world._rebuild_site_index()
    world._rebuild_route_index()
    world._validate_topology_integrity()
    world.atlas_layout = world._build_atlas_layout_from_current_state()
    world.propagation_rules["topology"]["mode"] = "travel"
    return world


def test_topology_acceptance_blocked_route_save_load_report_and_history(tmp_path) -> None:
    set_locale("en")
    world = _build_sparse_route_world()
    alpha = world.get_location_by_id("loc_alpha")
    bravo = world.get_location_by_id("loc_bravo")
    charlie = world.get_location_by_id("loc_charlie")
    assert alpha is not None
    assert bravo is not None
    assert charlie is not None

    alpha.danger = 90
    alpha.traffic = 80
    bravo_baseline_danger = world.location_state_defaults("loc_bravo", bravo.region_type)["danger"]
    bravo_baseline_traffic = world.location_state_defaults("loc_bravo", bravo.region_type)["traffic"]
    charlie_baseline_danger = world.location_state_defaults("loc_charlie", charlie.region_type)["danger"]
    charlie_baseline_traffic = world.location_state_defaults("loc_charlie", charlie.region_type)["traffic"]
    bravo.danger = bravo_baseline_danger
    bravo.traffic = bravo_baseline_traffic
    charlie.danger = charlie_baseline_danger
    charlie.traffic = charlie_baseline_traffic

    world.propagate_state(months=12)

    assert bravo.danger > bravo_baseline_danger
    assert bravo.traffic > bravo_baseline_traffic
    assert charlie.danger == charlie_baseline_danger
    assert charlie.traffic == charlie_baseline_traffic

    path = tmp_path / "sparse-route-world.json"
    sim = Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=0)
    assert save_simulation(sim, str(path)) is True

    restored = load_simulation(str(path))
    assert restored is not None
    restored_world = restored.world
    restored_world.routes[1].blocked = False

    restored_alpha = restored_world.get_location_by_id("loc_alpha")
    restored_charlie = restored_world.get_location_by_id("loc_charlie")
    assert restored_alpha is not None
    assert restored_charlie is not None
    restored_alpha.danger = 90
    restored_alpha.traffic = 80
    restored_world.propagate_state(months=12)

    assert restored_charlie.danger > 0
    assert restored_charlie.traffic > 0

    restored_world.record_event(
        WorldEventRecord(
            record_id="acceptance_route_opened",
            kind="journey",
            year=restored_world.year,
            month=1,
            day=1,
            location_id="loc_charlie",
            description="Travel reached Charlie after the road reopened.",
        )
    )

    monthly_report = generate_monthly_report(restored_world, restored_world.year, 1)
    assert [entry.location_id for entry in monthly_report.location_entries] == ["loc_charlie"]

    ctx = UIContext(inp=_PickThirdInput(), out=PrintRenderBackend())
    captured = io.StringIO()
    with redirect_stdout(captured):
        _show_location_history(restored_world, ctx=ctx)
    output = captured.getvalue()

    assert "Charlie" in output
    assert "1 recent event(s)" in output
