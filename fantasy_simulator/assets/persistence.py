"""Strict asset boundaries, including conservation of the finite initial caches."""

from collections import Counter
from copy import deepcopy
from typing import Any

from .models import Artifact, AssetRef, RESOURCES, identifier


def hydrate_ledger(ledger: Any, data: dict[str, Any]) -> Any:
    for row in data.get("stocks", []):
        key = (row["resource"], AssetRef.from_dict(row["owner"]), AssetRef.from_dict(row["holder"]))
        if key in ledger.stocks:
            raise ValueError("Duplicate stock holding")
        ledger.stocks[key] = row["quantity"]
    for row in data.get("artifacts", []):
        item = Artifact.from_dict(row)
        if item.artifact_id in ledger.artifacts:
            raise ValueError("Duplicate artifact ID")
        ledger.artifacts[item.artifact_id] = item
    sites = data.get("seeded_sites", [])
    if len(sites) != len(set(sites)):
        raise ValueError("Duplicate asset cache site")
    ledger.seeded_sites = set(sites)
    ledger.operations = deepcopy(data.get("operations", {}))
    validate_ledger(ledger)
    return ledger


def validate_ledger(ledger: Any) -> None:
    totals: Counter[str] = Counter()
    for (resource, owner, holder), quantity in ledger.stocks.items():
        if resource not in RESOURCES or type(quantity) is not int or quantity <= 0:
            raise ValueError("Invalid stock holding")
        if not isinstance(owner, AssetRef) or not isinstance(holder, AssetRef):
            raise ValueError("Invalid stock owner or custodian")
        totals[resource] += quantity
    expected = {"moon_silver": 20 * len(ledger.seeded_sites), "monster_trophy": 6 * len(ledger.seeded_sites)}
    if any(totals[resource] != quantity for resource, quantity in expected.items()):
        raise ValueError("Finite stock conservation violated")
    for site in ledger.seeded_sites:
        identifier(site, "cache site")
        if ledger.operations.get(f"cache:{site}", {}).get("site") != site:
            raise ValueError("Missing initial cache provenance")
    _validate_operations(ledger)
    _validate_stock_history(ledger)
    seen = set()
    for key, item in ledger.artifacts.items():
        identity = (item.origin_site_id, item.kind)
        if key != item.artifact_id or identity in seen or item.origin_site_id not in ledger.seeded_sites:
            raise ValueError("Invalid or duplicated artifact identity")
        seen.add(identity)
        if not isinstance(item.custodian, AssetRef) or (
            item.owner is not None and not isinstance(item.owner, AssetRef)
        ):
            raise ValueError("Invalid artifact owner or custodian")
        _validate_artifact_history(ledger, item)
    if len(seen) != 2 * len(ledger.seeded_sites):
        raise ValueError("A unique artifact was removed from its registry")


def _validate_operations(ledger: Any) -> None:
    for key, operation in ledger.operations.items():
        identifier(key, "asset operation")
        if operation.get("kind") not in ("initial_cache", "stock_transfer", "artifact_move", "ward_used"):
            raise ValueError("Unknown asset operation")
        event_id = operation.get("event_id")
        if event_id is not None:
            identifier(event_id, "asset event")
        if operation["kind"] != "initial_cache":
            ledger._validate_tick(operation.get("tick"))
        _validate_operation_provenance(ledger, key, operation)
        _operation_refs(operation)
        if operation["kind"] == "stock_transfer":
            if operation.get("resource") not in RESOURCES or type(operation.get("quantity")) is not int:
                raise ValueError("Invalid stock transfer history")
            if operation["quantity"] <= 0:
                raise ValueError("Invalid stock transfer quantity")


def _validate_operation_provenance(ledger: Any, key: str, operation: dict[str, Any]) -> None:
    if operation["kind"] in ("artifact_move", "ward_used"):
        if operation.get("artifact_id") not in ledger.artifacts:
            raise ValueError("Asset operation references an unknown artifact")
        if key not in ledger.artifacts[operation["artifact_id"]].history:
            raise ValueError("Artifact operation is missing from its provenance")
    if operation["kind"] == "initial_cache":
        if operation.get("site") not in ledger.seeded_sites or key != f"cache:{operation['site']}":
            raise ValueError("Invalid initial cache receipt")


def _validate_stock_history(ledger: Any) -> None:
    expected: Counter = Counter()
    for site_id in ledger.seeded_sites:
        site = AssetRef("site", site_id)
        expected[("moon_silver", site, site)] += 20
        expected[("monster_trophy", site, site)] += 6
    for operation in ledger.operations.values():
        if operation["kind"] == "stock_transfer":
            resource, quantity = operation["resource"], operation["quantity"]
            source = (resource, AssetRef.from_dict(operation["owner"]), AssetRef.from_dict(operation["holder"]))
            target = (resource, AssetRef.from_dict(operation["new_owner"]), AssetRef.from_dict(operation["new_holder"]))
            expected[source] -= quantity
            expected[target] += quantity
    if {key: quantity for key, quantity in expected.items() if quantity} != ledger.stocks:
        raise ValueError("Stock custody disagrees with transfer history")


def _validate_artifact_history(ledger: Any, item: Artifact) -> None:
    expected_seed = f"cache:{item.origin_site_id}"
    if not item.history or item.history[0] != expected_seed or len(item.history) != len(set(item.history)):
        raise ValueError("Invalid artifact provenance")
    uses = 0
    owner, holder = None, AssetRef("site", item.origin_site_id)
    for key in item.history:
        operation = ledger.operations.get(key)
        if operation is None or (key != expected_seed and operation.get("artifact_id") != item.artifact_id):
            raise ValueError("Broken artifact history reference")
        uses += operation["kind"] == "ward_used"
        if operation["kind"] == "artifact_move":
            owner = AssetRef.from_dict(operation["new_owner"]) if operation["new_owner"] else None
            holder = AssetRef.from_dict(operation["new_holder"])
        elif operation["kind"] == "ward_used" and AssetRef.from_dict(operation["holder"]) != holder:
            raise ValueError("Ward consumed by someone other than its custodian")
    if (item.owner, item.custodian) != (owner, holder):
        raise ValueError("Artifact custody disagrees with transfer history")
    initial = 3 if item.kind == "ancient_relic" else 0
    if item.charges != initial - uses:
        raise ValueError("Artifact charges disagree with consumption history")


def _operation_refs(operation: dict[str, Any]) -> set[AssetRef]:
    return {AssetRef.from_dict(operation[field]) for field in ("owner", "holder", "new_owner", "new_holder")
            if operation.get(field) is not None}


def _ledger_refs(ledger: Any) -> set[AssetRef]:
    refs = {AssetRef("site", site) for site in ledger.seeded_sites}
    for _, owner, holder in ledger.stocks:
        refs.update((owner, holder))
    for item in ledger.artifacts.values():
        refs.add(item.custodian)
        if item.owner is not None:
            refs.add(item.owner)
        if item.maker_id:
            refs.add(AssetRef("character", item.maker_id))
    for operation in ledger.operations.values():
        refs.update(_operation_refs(operation))
    return refs


def validate_asset_references(world: Any, *, characters: bool = True) -> None:
    ledger = world.assets
    validate_ledger(ledger)
    for ref in _ledger_refs(ledger):
        if ref.kind == "site" and world.get_location_by_id(ref.reference_id) is None:
            raise ValueError("Asset references an unknown site")
        if characters and ref.kind == "character" and world.get_character_by_id(ref.reference_id) is None:
            raise ValueError("Asset references an unknown character")
    records = {record.record_id: record for record in world.event_records}
    for key, operation in ledger.operations.items():
        event_id = operation.get("event_id")
        if event_id is not None:
            record = records.get(event_id)
            if record is None or key not in record.render_params.get("asset_operations", []):
                raise ValueError("Asset history disagrees with its canonical event")
