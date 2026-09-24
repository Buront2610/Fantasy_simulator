"""A single carrier's finite shipment, backed exclusively by the asset ledger."""

from copy import deepcopy
from dataclasses import replace
from typing import Any

from ..assets.models import AssetRef
from ..i18n import tr
from .results import AdventureStepResult, step_fact_result


def load_cargo(world: Any, run: Any, tick: int) -> list[str]:
    cargo = run.objective.cargo
    if cargo is None:
        return []
    cargo.validate()
    carrier = world.get_character_by_id(run.character_id)
    if (cargo.state != "planned" or not carrier.alive or carrier.active_adventure_id is not None
            or carrier.injury_status != "none" or carrier.location_id != run.origin
            or run.origin == run.destination or run.member_ids != [run.character_id]):
        raise ValueError("Transport requires one available, healthy owner at a distinct departure site")
    owner = AssetRef("character", run.character_id)
    source = owner if cargo.source_kind == "character" else AssetRef("site", run.origin)
    # Starts mutate live objects inside AdventureTransaction: replace, never mutate its retained ledger.
    ledger = deepcopy(world.assets)
    operation = f"cargo:{run.adventure_id}:load"
    ledger.transfer_stock(cargo.resource, owner, source, owner, owner, cargo.quantity,
                          operation_id=operation, tick=tick)
    world.assets = ledger
    cargo.state = "in_transit"
    return [operation]


def deliver_cargo(world: Any, run: Any) -> AdventureStepResult | None:
    goal = run.objective
    if goal is None or goal.purpose != "transport":
        return None
    cargo = goal.cargo
    if (goal.status != "active" or cargo.state != "in_transit"
            or run.itinerary.current_site_id != run.destination or run.itinerary.active_leg is not None):
        raise ValueError("Delivery requires a pending shipment physically at its destination")
    owner, site = AssetRef("character", run.character_id), AssetRef("site", run.destination)
    if world.assets.stocks.get((cargo.resource, owner, owner), 0) < cargo.quantity:
        goal.status, run.state = "failed", "returning"
        result = step_fact_result(run, "adventure_cargo_missing", "summary_adventure_cargo_missing",
                                  {"name": run.character_name}, severity=2)
        run._record(result.facts[0].description, result.facts[0].description)
        return result
    operation = f"cargo:{run.adventure_id}:deliver"
    world.assets.transfer_stock(cargo.resource, owner, owner, owner, site, cargo.quantity,
                                operation_id=operation, tick=world.tick)
    cargo.state, goal.status, run.state = "delivered", "completed", "returning"
    run.pending_choice = None
    result = step_fact_result(run, "adventure_cargo_delivered", "summary_adventure_cargo_delivered",
                              {"name": run.character_name, "resource": tr(f"assets.kind_{cargo.resource}"),
                               "quantity": cargo.quantity, "destination": world.location_name(run.destination),
                               "asset_operations": [operation], "resource_key": cargo.resource}, severity=2)
    run._record(result.facts[0].description, result.facts[0].description)
    return result


def complete_cargo_return(world: Any, run: Any, carrier: Any) -> AdventureStepResult | None:
    cargo = run.objective.cargo if run.objective is not None else None
    if cargo is None or cargo.state != "delivered" or not carrier.alive or carrier.injury_status != "none":
        return None
    if carrier.location_id != run.origin:
        raise ValueError("Carrier has not returned to the origin")
    run.steps_taken += 1
    run.state, run.outcome, run.resolution_year = "resolved", "safe_return", world.year
    run.injury_status, run.injury_member_id = "none", None
    run._clear_member_adventures(world)
    result = step_fact_result(run, "adventure_cargo_returned", "summary_adventure_cargo_returned",
                              {"name": carrier.name}, location_id=run.origin)
    run._record(result.facts[0].description, result.facts[0].description)
    carrier.add_history(tr("history_adventure_detail", year=world.year, detail=result.facts[0].description))
    return result


def settle_cargo(world: Any, run: Any, result: AdventureStepResult) -> AdventureStepResult:
    """Unload an unsuccessful returned shipment; a dead carrier retains physical custody."""
    cargo = run.objective.cargo if run.objective is not None else None
    if cargo is None or cargo.state != "in_transit" or not run.is_resolved:
        return result
    owner = AssetRef("character", run.character_id)
    carrier = world.get_character_by_id(run.character_id)
    quantity = min(cargo.quantity, world.assets.stocks.get((cargo.resource, owner, owner), 0))
    operations = []
    if carrier.alive and carrier.location_id == run.origin and quantity:
        operation = f"cargo:{run.adventure_id}:return"
        world.assets.transfer_stock(cargo.resource, owner, owner, owner, AssetRef("site", run.origin), quantity,
                                    operation_id=operation, tick=world.tick)
        operations.append(operation)
        cargo.state = "returned" if quantity == cargo.quantity else "stranded"
    else:
        cargo.state = "stranded"
    run.objective.status = "failed"
    if operations:
        first, *rest = result.facts
        params = {**first.render_params,
                  "asset_operations": [*first.render_params.get("asset_operations", []), *operations]}
        result = replace(result, facts=(replace(first, render_params=params), *rest))
    return result
