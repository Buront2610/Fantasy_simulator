"""Save-boundary checks tying each shipment to actual ledger transfers."""

from typing import Any

from ..assets.models import AssetRef


def validate_cargo_shipments(world: Any) -> None:
    for run in (*world.active_adventures, *world.completed_adventures):
        goal = run.objective
        if goal is None or goal.cargo is None:
            continue
        goal.validate()
        cargo = goal.cargo
        if run.member_ids != [run.character_id] or cargo.state == "planned":
            raise ValueError("Saved transport must be a dispatched single-carrier shipment")
        expected_resolved = cargo.state in ("returned", "stranded")
        if cargo.state != "delivered" and run.is_resolved != expected_resolved:
            raise ValueError("Cargo state conflicts with adventure resolution")
        owner = AssetRef("character", run.character_id)
        source = owner if cargo.source_kind == "character" else AssetRef("site", run.origin)
        _require_transfer(world, run, "load", owner, source, owner)
        delivery = world.assets.operations.get(f"cargo:{run.adventure_id}:deliver")
        if cargo.state == "delivered":
            _require_transfer(world, run, "deliver", owner, owner, AssetRef("site", run.destination))
        elif delivery is not None:
            raise ValueError("Delivery receipt conflicts with shipment state")
        if cargo.state == "returned":
            _require_transfer(world, run, "return", owner, owner, AssetRef("site", run.origin))


def _require_transfer(world: Any, run: Any, action: str, owner: AssetRef,
                      source: AssetRef, target: AssetRef) -> None:
    cargo = run.objective.cargo
    op = world.assets.operations.get(f"cargo:{run.adventure_id}:{action}", {})
    expected = {"kind": "stock_transfer", "resource": cargo.resource, "quantity": cargo.quantity,
                "owner": owner.to_dict(), "holder": source.to_dict(),
                "new_owner": owner.to_dict(), "new_holder": target.to_dict()}
    if any(op.get(key) != value for key, value in expected.items()) or not op.get("event_id"):
        raise ValueError("Shipment disagrees with its canonical stock transfer")
