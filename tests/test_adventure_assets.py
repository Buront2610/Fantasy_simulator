"""Finite rewards, physical custody, consumed wards, and atomic persistence."""

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from fantasy_simulator.adventure.itinerary import AdventureItinerary
from fantasy_simulator.adventure.policy import AdventurePolicyEngine
from fantasy_simulator.adventure.rewards import find_discovery, ward_injury
from fantasy_simulator.adventure.combat import AdventureHazardResult
from fantasy_simulator.assets.ledger import AssetLedger
from fantasy_simulator.assets.models import Artifact, AssetRef
from fantasy_simulator.simulation import Simulator
from fantasy_simulator.ui.asset_presenter import asset_lines
from fantasy_simulator.world_history.retention import compact_world_history
from tests.test_adventure_routes import expedition, advance_due  # noqa: F401


@pytest.fixture
def at_cache(expedition, monkeypatch):  # noqa: F811
    sim, run, hero = expedition
    monkeypatch.setattr(AdventurePolicyEngine, "compute_injury_chance", lambda *_: 0)
    monkeypatch.setattr(AdventurePolicyEngine, "compute_loot_chance", lambda *_: 1)
    monkeypatch.setattr(sim.rng, "random", lambda: 0.9)
    monkeypatch.setattr(sim.rng, "choice", lambda values: list(values)[0])
    advance_due(sim, run)
    advance_due(sim, run)
    assert run.state == "exploring"
    return sim, run, hero


def test_discovery_makes_one_real_item_and_return_does_not_duplicate_it(at_cache):
    sim, run, hero = at_cache
    advance_due(sim, run)
    item = next(item for item in sim.world.assets.artifacts.values() if item.kind == "ancient_relic")
    assert item.owner == item.custodian == AssetRef("character", hero.char_id)
    assert item.charges == 3 and len(sim.world.assets.artifacts) == 2
    found = sim.world.event_records[-1]
    assert found.kind == "adventure_discovery" and found.render_params["artifact_ids"] == [item.artifact_id]
    before = deepcopy(sim.world.assets.to_dict())
    restored = Simulator.from_dict(sim.to_dict())
    run = restored.world.get_adventure_by_id(run.adventure_id)
    for _ in range(10):
        if run.is_resolved:
            break
        advance_due(restored, run)
    assert run.is_resolved and restored.world.get_character_by_id(hero.char_id).location_id == "home"
    assert restored.world.assets.to_dict() == before
    assert item.artifact_id in " ".join(asset_lines(restored.world, item.owner))


def test_finite_cache_does_not_refill_after_exhaustion_or_reload(at_cache):
    sim, run, hero = at_cache
    world = SimpleNamespace(assets=sim.world.assets, tick=1)
    rewards = []
    for step in range(1, 10):
        run.steps_taken = step
        result = find_discovery(world, run, [hero], SimpleNamespace(choice=lambda values: values[0]))
        if result:
            rewards.append(result)
    assert len(rewards) == 6  # one ward, two silver batches, one fragment, two material batches
    assert sum(world.assets.stocks.values()) == 26
    assert all(key[2] == AssetRef("character", hero.char_id) for key in world.assets.stocks)
    world.assets = AssetLedger.from_dict(world.assets.to_dict())
    assert find_discovery(world, run, [hero], SimpleNamespace(choice=lambda values: values[0])) is None
    assert len(world.assets.artifacts) == 2


def test_stock_moves_once_and_rejects_conflicting_replay():
    ledger = AssetLedger()
    ledger.seed_site("site")
    site, person = AssetRef("site", "site"), AssetRef("character", "person")
    kwargs = dict(operation_id="shipment", tick=2)
    assert ledger.transfer_stock("moon_silver", site, site, person, person, 10, **kwargs)
    assert not ledger.transfer_stock("moon_silver", site, site, person, person, 10, **kwargs)
    with pytest.raises(ValueError, match="different request"):
        ledger.transfer_stock("moon_silver", site, site, person, person, 11, **kwargs)
    assert ledger.stocks[("moon_silver", person, person)] == 10
    assert sum(q for key, q in ledger.stocks.items() if key[0] == "moon_silver") == 20


def test_loss_and_rediscovery_preserve_identity_and_owner(at_cache):
    sim, run, hero = at_cache
    advance_due(sim, run)
    ledger = sim.world.assets
    item = next(item for item in ledger.artifacts.values() if item.owner is not None)
    owner, site = item.owner, AssetRef("site", "dungeon")
    ledger.drop_carried(owner, site, operation_id="lost", tick=10)
    assert ledger.artifacts[item.artifact_id].owner == owner
    other = AssetRef("character", "other")
    ledger.move_artifact(item.artifact_id, owner, other, operation_id="found", tick=11, reason="recovered")
    recovered = AssetLedger.from_dict(ledger.to_dict()).artifacts[item.artifact_id]
    assert recovered.artifact_id == item.artifact_id and recovered.owner == owner and recovered.custodian == other
    assert recovered.origin_site_id == item.origin_site_id
    assert len(ledger.artifacts) == 2
    assert recovered.history[-1] == "found"


def test_ward_reduces_real_injury_three_times_then_exhausts(at_cache, monkeypatch):
    sim, run, hero = at_cache
    advance_due(sim, run)
    artifact_id = next(key for key, item in sim.world.assets.artifacts.items() if item.owner is not None)
    monkeypatch.setattr(AdventurePolicyEngine, "compute_injury_chance", lambda *_: 1)
    monkeypatch.setattr("fantasy_simulator.adventure.hazards.resolve_adventure_hazard_combat",
                        lambda *_: AdventureHazardResult(1, "test hazard", 1, False))
    run.schedule.deadline_tick = 1000
    run.schedule.initial_provisions = run.schedule.provisions = 1000
    for remaining in (2, 1, 0, 0):
        run.state = "exploring"
        run.itinerary = AdventureItinerary(run.destination, visited_destination=True)
        hero.location_id = run.destination
        advance_due(sim, run)
        assert sim.world.assets.artifacts[artifact_id].charges == remaining
    assert hero.injury_status == "injured"
    uses = [op for op in sim.world.assets.operations.values() if op["kind"] == "ward_used"]
    assert len(uses) == 3 and all(op["event_id"] for op in uses)
    assert Simulator.from_dict(sim.to_dict()).world.assets.artifacts[artifact_id].charges == 0


def test_failed_fact_recording_rolls_back_assets_and_retry_is_once(at_cache, monkeypatch):
    sim, run, hero = at_cache
    before, rng = sim.to_dict(), sim.rng.getstate()
    original = sim._record_adventure_step_result

    def fail(*args):
        original(*args)
        raise RuntimeError("after asset event")

    monkeypatch.setattr(sim, "_record_adventure_step_result", fail)
    with pytest.raises(RuntimeError, match="after asset event"):
        advance_due(sim, run)
    assert sim.world.assets.to_dict() == before["world"].get("assets", AssetLedger().to_dict())
    assert sim.rng.getstate() == rng and run.state == "exploring"
    monkeypatch.setattr(sim, "_record_adventure_step_result", original)
    advance_due(sim, run)
    assert len(sim.world.assets.artifacts) == 2
    assert sum(item.owner == AssetRef("character", hero.char_id) for item in sim.world.assets.artifacts.values()) == 1


@pytest.mark.parametrize("damage", ["duplicate", "quantity", "charges", "owner", "history", "custody", "event"])
def test_corrupt_asset_save_is_rejected(at_cache, damage):
    sim, run, _ = at_cache
    advance_due(sim, run)
    data = sim.to_dict()
    assets = data["world"]["assets"]
    if damage == "duplicate":
        assets["artifacts"].append(deepcopy(assets["artifacts"][0]))
    elif damage == "quantity":
        assets["stocks"][0]["quantity"] += 1
    elif damage == "charges":
        next(item for item in assets["artifacts"] if item["kind"] == "ancient_relic")["charges"] = 1
    elif damage == "owner":
        assets["artifacts"][0]["owner"] = {"kind": "character", "id": "missing"}
    elif damage == "custody":
        assets["stocks"][0]["holder"] = {"kind": "site", "id": "home"}
    elif damage == "event":
        next(op for op in assets["operations"].values() if op["kind"] == "artifact_move")["event_id"] = (
            sim.world.event_records[0].record_id
        )
    else:
        assets["artifacts"][0]["history"].append("missing")
    with pytest.raises(ValueError):
        Simulator.from_dict(data)


def test_asset_provenance_survives_history_retention(at_cache):
    sim, run, _ = at_cache
    advance_due(sim, run)
    event_id = sim.world.event_records[-1].record_id
    for i in range(10):
        sim._record_world_event(str(i), kind="meeting", location_id="home")
    compact_world_history(sim.world, max_event_records=1, max_completed_adventures=0)
    assert event_id in {record.record_id for record in sim.world.event_records}
    assert Simulator.from_dict(sim.to_dict()).world.assets.artifacts


def test_legacy_text_rewards_do_not_create_assets(at_cache):
    sim, run, hero = at_cache
    run.objective = None
    advance_due(sim, run)
    assert run.loot_summary and not sim.world.assets.artifacts
    assert "assets" not in sim.to_dict()["world"]


def test_heavy_injury_drops_real_items_and_discovery_recovers_them(at_cache, monkeypatch):
    sim, run, hero = at_cache
    advance_due(sim, run)
    artifact_id = next(key for key, item in sim.world.assets.artifacts.items() if item.owner is not None)
    owner = AssetRef("character", hero.char_id)
    run.state = "exploring"
    run.itinerary = AdventureItinerary(run.destination, visited_destination=True)
    monkeypatch.setattr(AdventurePolicyEngine, "compute_injury_chance", lambda *_: 1)
    monkeypatch.setattr("fantasy_simulator.adventure.hazards.resolve_adventure_hazard_combat",
                        lambda *_: AdventureHazardResult(3, "test hazard", 1, False))
    advance_due(sim, run)
    item = sim.world.assets.artifacts[artifact_id]
    assert hero.injury_status == "serious"
    assert item.charges == 2 and item.owner == owner and item.custodian == AssetRef("site", "dungeon")
    assert sim.world.assets.operations[item.history[-1]]["event_id"] == sim.world.event_records[-1].record_id
    restored = Simulator.from_dict(sim.to_dict())
    world = SimpleNamespace(assets=restored.world.assets, tick=100)
    run.steps_taken += 1
    reward = find_discovery(world, run, [SimpleNamespace(alive=True, char_id="rescuer")],
                            SimpleNamespace(choice=lambda values: values[0]))
    recovered = world.assets.artifacts[artifact_id]
    assert reward.details["artifact_ids"] == [artifact_id]
    assert recovered.owner == owner and recovered.custodian == AssetRef("character", "rescuer")
    assert recovered.charges == 2 and len(world.assets.artifacts) == 2


def test_resource_distribution_preserves_integer_remainder(at_cache):
    sim, run, _ = at_cache
    members = [SimpleNamespace(alive=True, char_id=f"member-{i}") for i in range(3)]
    reward = find_discovery(SimpleNamespace(assets=sim.world.assets, tick=1), run, members,
                            SimpleNamespace(choice=lambda _: "moon_silver"))
    assert reward.details["resource_shares"] == {"member-0": 4, "member-1": 3, "member-2": 3}
    assert sum(sim.world.assets.stocks.values()) == 26
    assert AssetLedger.from_dict(sim.world.assets.to_dict()).stocks == sim.world.assets.stocks


def test_ward_does_not_consume_on_unharmed_result_and_rolls_back_failed_injury(at_cache, monkeypatch):
    sim, run, hero = at_cache
    advance_due(sim, run)
    before = deepcopy(sim.world.assets.to_dict())
    assert ward_injury(SimpleNamespace(assets=sim.world.assets, tick=1), run, hero, 0) == (0, {})
    assert sim.world.assets.to_dict() == before
    run.state = "exploring"
    run.itinerary = AdventureItinerary(run.destination, visited_destination=True)
    monkeypatch.setattr(AdventurePolicyEngine, "compute_injury_chance", lambda *_: 1)
    monkeypatch.setattr("fantasy_simulator.adventure.hazards.resolve_adventure_hazard_combat",
                        lambda *_: AdventureHazardResult(3, "test hazard", 1, False))
    original = sim._record_adventure_step_result

    def fail(*args):
        original(*args)
        raise RuntimeError("after ward and drop")

    monkeypatch.setattr(sim, "_record_adventure_step_result", fail)
    with pytest.raises(RuntimeError, match="after ward and drop"):
        advance_due(sim, run)
    assert sim.world.assets.to_dict() == before and hero.injury_status == "none"
    assert run.state == "exploring"


def test_artifact_preserves_known_history_text_without_inventing_unknown_metadata():
    ledger = AssetLedger()
    ledger.seed_site("ruin")
    item = ledger.artifacts["artifact:ruin:lore"]
    restored = Artifact.from_dict(item.to_dict())
    assert restored.maker_id is None and restored.creation_year is None and restored.inscription == ""
    known = replace(item, maker_id="scribe", creation_year=12, inscription="A name from the old era",
                    inscription_language="old-tongue", inscription_stage="early")
    assert Artifact.from_dict(known.to_dict()) == known


def _join_party(sim, run, char_id, **stats):
    from fantasy_simulator.character import Character
    member = Character(char_id.title(), 30, "Female", "Human", "Warrior", char_id=char_id,
                       location_id=run.destination, **stats)
    sim.world.add_character(member)
    member.active_adventure_id = run.adventure_id
    run.member_ids.append(member.char_id)
    return member


def _hazard_step(sim, run, hero, monkeypatch, severity):
    run.state = "exploring"
    run.itinerary = AdventureItinerary(run.destination, visited_destination=True)
    hero.location_id = run.destination
    monkeypatch.setattr(AdventurePolicyEngine, "compute_injury_chance", lambda *_: 1)
    monkeypatch.setattr("fantasy_simulator.adventure.hazards.resolve_adventure_hazard_combat",
                        lambda *_: AdventureHazardResult(severity, "test hazard", 1, False))
    advance_due(sim, run)


def test_ward_carried_by_companion_protects_injured_frontline(at_cache, monkeypatch):
    sim, run, hero = at_cache
    advance_due(sim, run)
    artifact_id = next(key for key, item in sim.world.assets.artifacts.items() if item.owner is not None)
    front = _join_party(sim, run, "front", strength=95, constitution=95)
    _hazard_step(sim, run, hero, monkeypatch, 1)
    item = sim.world.assets.artifacts[artifact_id]
    assert front.injury_status == "none" and item.charges == 2
    assert item.custodian == AssetRef("character", hero.char_id)
    use = sim.world.assets.operations[item.history[-1]]
    assert use["holder"] == {"kind": "character", "id": hero.char_id}
    assert use["protected"] == {"kind": "character", "id": front.char_id}
    record = sim.world.event_records[-1]
    assert record.primary_actor_id == front.char_id and record.render_params["ward_holder_id"] == hero.char_id
    restored = Simulator.from_dict(sim.to_dict())
    assert restored.world.assets.operations[item.history[-1]]["protected"]["id"] == front.char_id


def test_dead_companion_ward_does_not_protect_party(at_cache, monkeypatch):
    sim, run, hero = at_cache
    advance_due(sim, run)
    artifact_id = next(key for key, item in sim.world.assets.artifacts.items() if item.owner is not None)
    front = _join_party(sim, run, "front", strength=95, constitution=95)
    hero.alive = False
    world = SimpleNamespace(assets=sim.world.assets, tick=1, get_character_by_id=sim.world.get_character_by_id)
    assert ward_injury(world, run, front, 1) == (1, {})
    assert sim.world.assets.artifacts[artifact_id].charges == 3


def test_hit_that_leaves_carrier_seriously_hurt_drops_items(at_cache, monkeypatch):
    sim, run, hero = at_cache
    advance_due(sim, run)
    artifact_id = next(key for key, item in sim.world.assets.artifacts.items() if item.owner is not None)
    hero.injury_status = "injured"
    _hazard_step(sim, run, hero, monkeypatch, 2)
    item = sim.world.assets.artifacts[artifact_id]
    assert hero.injury_status == "serious" and item.charges == 2
    assert item.custodian == AssetRef("site", "dungeon") and item.owner == AssetRef("character", hero.char_id)


def test_hit_that_leaves_carrier_only_injured_keeps_items(at_cache, monkeypatch):
    sim, run, hero = at_cache
    advance_due(sim, run)
    artifact_id = next(key for key, item in sim.world.assets.artifacts.items() if item.owner is not None)
    _hazard_step(sim, run, hero, monkeypatch, 2)
    item = sim.world.assets.artifacts[artifact_id]
    assert hero.injury_status == "injured" and item.charges == 2
    assert item.custodian == AssetRef("character", hero.char_id)


def test_moving_unknown_artifact_is_rejected_as_invalid_reference():
    ledger = AssetLedger()
    with pytest.raises(ValueError, match="Unknown artifact"):
        ledger.move_artifact("artifact:none", None, AssetRef("site", "x"), operation_id="op", tick=1,
                             reason="discovered")
