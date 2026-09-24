"""Physical cargo, arrival idempotence, route failure, and saved transaction recovery."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from fantasy_simulator.adventure.cargo import deliver_cargo
from fantasy_simulator.adventure.policy import AdventurePolicyEngine
from fantasy_simulator.assets.models import AssetRef
from fantasy_simulator.character import Character
from fantasy_simulator.character_model.death_resolution import mark_character_dead
from fantasy_simulator.simulation import Simulator
from fantasy_simulator.simulation.cargo_dispatch import start_transport
from fantasy_simulator.terrain import RouteEdge
from fantasy_simulator.ui.screen_cargo import request_cargo_transport
from fantasy_simulator.ui.screen_results import _update_dirty_state_for_action
from fantasy_simulator.world import LocationState, World
from tests.test_adventure_routes import advance_due


@pytest.fixture
def cargo_world(monkeypatch):
    world = World(_skip_defaults=True, width=3, height=1)
    for i, site in enumerate(("home", "waypoint", "destination")):
        world._register_location(LocationState(site, site, "cargo test", "village",
                                               i, 0, 50, 50, 50, 20, 10, 10, 50))
    world._build_terrain_from_grid()
    world.routes = [RouteEdge("hw", "home", "waypoint"), RouteEdge("wd", "waypoint", "destination", distance=2)]
    hero = Character("Carrier", 25, "Male", "Human", "Warrior", char_id="carrier", location_id="home")
    world.add_character(hero)
    sim = Simulator(world, seed=23, adventure_steps_per_year=360)
    world.assets.seed_site("home")
    owner, site = AssetRef("character", hero.char_id), AssetRef("site", "home")
    world.assets.transfer_stock("moon_silver", site, site, owner, site, 10, operation_id="claim", tick=0)
    monkeypatch.setattr(sim.rng, "random", lambda: 0.9)
    monkeypatch.setattr(AdventurePolicyEngine, "compute_injury_chance", lambda *_: 0)
    return sim, hero


def depart(sim, hero, quantity=6):
    return start_transport(sim, hero.char_id, "destination", "moon_silver", quantity, source_kind="site")


def finish(sim, run):
    for _ in range(20):
        if run.is_resolved:
            return
        if run.pending_choice:
            sim.resolve_adventure_choice(run.adventure_id, "press_on")
        else:
            advance_due(sim, run)
    pytest.fail("Transport did not finish")


def test_stock_is_physically_loaded_and_delivered_only_once(cargo_world):
    sim, hero = cargo_world
    site = sim.world.get_location_by_id("destination")
    progress = (site.exploration_progress, site.adventure_reputation, site.dungeon_clearance)
    run = depart(sim, hero)
    owner = AssetRef("character", hero.char_id)
    assert sim.world.assets.stocks[("moon_silver", owner, owner)] == 6
    assert sim.world.assets.stocks[("moon_silver", owner, AssetRef("site", "home"))] == 4
    assert ("moon_silver", owner, AssetRef("site", "destination")) not in sim.world.assets.stocks
    advance_due(sim, run)
    assert hero.location_id == "waypoint" and sim.world.character_presence_location_id(hero) is None
    restored = Simulator.from_dict(sim.to_dict())
    restored.rng.random = lambda: 0.9
    new_run = restored.world.get_adventure_by_id(run.adventure_id)
    finish(restored, new_run)
    ledger = restored.world.assets
    assert new_run.objective.cargo.state == "delivered" and new_run.objective.status == "completed"
    assert new_run.outcome == "safe_return" and not new_run.loot_summary
    site = restored.world.get_location_by_id("destination")
    assert (site.exploration_progress, site.adventure_reputation, site.dungeon_clearance) == progress
    assert ledger.stocks[("moon_silver", owner, AssetRef("site", "destination"))] == 6
    assert sum(ledger.stocks.values()) == 26
    assert not any(key.startswith(f"cargo:{run.adventure_id}:return") for key in ledger.operations)
    before = ledger.to_dict()
    with pytest.raises(ValueError):
        deliver_cargo(SimpleNamespace(assets=ledger, tick=100), new_run)
    assert ledger.to_dict() == before
    assert Simulator.from_dict(restored.to_dict()).world.assets.to_dict() == before


def test_blocked_route_returns_original_goods_without_teleport(cargo_world):
    sim, hero = cargo_world
    run = depart(sim, hero)
    sim.world.routes = [sim.world.routes[0]]
    finish(sim, run)
    assert run.objective.cargo.state == "returned" and run.objective.status == "failed"
    owner = AssetRef("character", hero.char_id)
    assert hero.location_id == "home"
    assert sim.world.assets.stocks[("moon_silver", owner, AssetRef("site", "home"))] == 10
    assert ("moon_silver", owner, AssetRef("site", "destination")) not in sim.world.assets.stocks
    Simulator.from_dict(sim.to_dict())


@pytest.mark.parametrize("bad_quantity", [0, -1, 11, True, 1.5])
def test_invalid_request_does_not_mutate_world_or_rng(cargo_world, bad_quantity):
    sim, hero = cargo_world
    before, rng = sim.to_dict(), sim.id_rng.getstate()
    with pytest.raises(ValueError):
        depart(sim, hero, bad_quantity)
    assert sim.to_dict() == before and sim.id_rng.getstate() == rng


def test_departure_failure_restores_inventory_and_actor(cargo_world, monkeypatch):
    sim, hero = cargo_world
    before = sim.to_dict()
    original = sim._record_world_event

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("after loading")

    monkeypatch.setattr(sim, "_record_world_event", fail)
    with pytest.raises(RuntimeError, match="after loading"):
        depart(sim, hero)
    assert sim.to_dict() == before and hero.active_adventure_id is None
    monkeypatch.setattr(sim, "_record_world_event", original)
    assert depart(sim, hero).objective.cargo.state == "in_transit"


def test_delivery_failure_rolls_back_and_retry_delivers_once(cargo_world, monkeypatch):
    sim, hero = cargo_world
    run = depart(sim, hero)
    advance_due(sim, run)
    advance_due(sim, run)
    assert run.state == "exploring"
    before = deepcopy(sim.world.assets.to_dict())
    original = sim._record_adventure_step_result

    def fail(*args):
        original(*args)
        raise RuntimeError("after delivery")

    monkeypatch.setattr(sim, "_record_adventure_step_result", fail)
    with pytest.raises(RuntimeError, match="after delivery"):
        advance_due(sim, run)
    assert sim.world.assets.to_dict() == before and run.objective.cargo.state == "in_transit"
    monkeypatch.setattr(sim, "_record_adventure_step_result", original)
    finish(sim, run)
    assert sum(op["kind"] == "stock_transfer" and key.endswith(":deliver")
               for key, op in sim.world.assets.operations.items()) == 1


def test_corrupt_manifest_is_rejected_on_load(cargo_world):
    sim, hero = cargo_world
    depart(sim, hero)
    data = sim.to_dict()
    data["world"]["active_adventures"][0]["objective"]["cargo"]["quantity"] = 7
    with pytest.raises(ValueError, match="Shipment disagrees"):
        Simulator.from_dict(data)


def test_ui_dispatch_marks_dirty_only_after_real_departure(cargo_world):
    sim, hero = cargo_world
    output = []
    answers = iter(["1", "1", "3"])
    ctx = SimpleNamespace(inp=SimpleNamespace(read_line=lambda _: next(answers), pause=lambda: None),
                          out=SimpleNamespace(print_line=output.append, print_warning=output.append,
                                              print_dim=output.append))
    assert _update_dirty_state_for_action("transport_cargo", sim, ctx)
    assert sim.world.active_adventures[-1].objective.cargo.quantity == 3
    assert not request_cargo_transport(sim, ctx)  # Busy owners cannot dispatch twice.


def test_external_death_keeps_cargo_with_carrier_and_remains_saveable(cargo_world):
    sim, hero = cargo_world
    run = depart(sim, hero)
    before = sim.world.assets.to_dict()
    mark_character_dead(hero, sim.world)
    assert run.objective.cargo.state == "stranded" and run.objective.status == "failed"
    assert sim.world.assets.to_dict() == before
    assert Simulator.from_dict(sim.to_dict()).world.assets.to_dict() == before


def test_cancelling_dispatch_preserves_existing_unsaved_changes(cargo_world):
    sim, _ = cargo_world
    ctx = SimpleNamespace(inp=SimpleNamespace(read_line=lambda _: "", pause=lambda: None),
                          out=SimpleNamespace(print_line=lambda _: None))
    assert _update_dirty_state_for_action("transport_cargo", sim, ctx, current_dirty=True)
    assert not _update_dirty_state_for_action("transport_cargo", sim, ctx, current_dirty=False)
    assert not sim.world.active_adventures


def test_lost_cargo_cannot_be_fabricated_at_destination(cargo_world):
    sim, hero = cargo_world
    run = depart(sim, hero)
    owner = AssetRef("character", hero.char_id)
    sim.world.assets.drop_carried(owner, AssetRef("site", "home"), operation_id="loss", tick=1)
    finish(sim, run)
    assert run.objective.status == "failed" and run.objective.cargo.state == "stranded"
    assert sim.world.assets.stocks[("moon_silver", owner, AssetRef("site", "home"))] == 10
    assert ("moon_silver", owner, AssetRef("site", "destination")) not in sim.world.assets.stocks
    Simulator.from_dict(sim.to_dict())
