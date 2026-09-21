"""Finite balances and single-owner artifacts; operation IDs prevent duplicate writes."""

from copy import deepcopy
from dataclasses import replace
from typing import Any

from .models import Artifact, AssetRef, RESOURCES, identifier

StockKey = tuple[str, AssetRef, AssetRef]


class AssetLedger:
    def __init__(self) -> None:
        self.stocks: dict[StockKey, int] = {}
        self.artifacts: dict[str, Artifact] = {}
        self.seeded_sites: set[str] = set()
        self.operations: dict[str, dict[str, Any]] = {}

    def _already_applied(self, operation_id: str, request: dict[str, Any]) -> bool:
        identifier(operation_id, "asset operation")
        previous = self.operations.get(operation_id)
        if previous is None:
            return False
        if {key: value for key, value in previous.items() if key != "event_id"} != request:
            raise ValueError("Asset operation ID reused with a different request")
        return True

    def seed_site(self, site_id: str) -> None:
        identifier(site_id, "asset site")
        if site_id in self.seeded_sites:
            return
        site = AssetRef("site", site_id)
        op = f"cache:{site_id}"
        if op in self.operations:
            raise ValueError("Asset cache receipt conflicts with unseeded site")
        artifacts = [Artifact(f"artifact:{site_id}:ward", "ancient_relic", site_id, site, charges=3,
                              material="moonstone", purpose="protection", history=(op,)),
                     Artifact(f"artifact:{site_id}:lore", "lore_fragment", site_id, site,
                              material="vellum", purpose="archive", history=(op,))]
        if any(item.artifact_id in self.artifacts for item in artifacts):
            raise ValueError("Duplicate initial artifact ID")
        self.stocks[("moon_silver", site, site)] = self.stocks.get(("moon_silver", site, site), 0) + 20
        self.stocks[("monster_trophy", site, site)] = self.stocks.get(("monster_trophy", site, site), 0) + 6
        self.artifacts.update((item.artifact_id, item) for item in artifacts)
        self.seeded_sites.add(site_id)
        self.operations[op] = {"kind": "initial_cache", "site": site_id, "event_id": None}

    def transfer_stock(self, resource: str, owner: AssetRef, holder: AssetRef, new_owner: AssetRef,
                       new_holder: AssetRef, quantity: int, *, operation_id: str, tick: int) -> bool:
        if resource not in RESOURCES or type(quantity) is not int or quantity <= 0:
            raise ValueError("Stock transfer requires a known resource and positive integer quantity")
        request = {"kind": "stock_transfer", "resource": resource, "quantity": quantity, "tick": tick,
                   "owner": owner.to_dict(), "holder": holder.to_dict(),
                   "new_owner": new_owner.to_dict(), "new_holder": new_holder.to_dict()}
        self._validate_tick(tick)
        if self._already_applied(operation_id, request):
            return False
        source, target = (resource, owner, holder), (resource, new_owner, new_holder)
        available = self.stocks.get(source, 0)
        if quantity > available:
            raise ValueError("Insufficient stock")
        if source != target:
            if available == quantity:
                del self.stocks[source]
            else:
                self.stocks[source] = available - quantity
            self.stocks[target] = self.stocks.get(target, 0) + quantity
        self.operations[operation_id] = {**request, "event_id": None}
        return True

    def move_artifact(self, artifact_id: str, owner: AssetRef | None, holder: AssetRef, *,
                      operation_id: str, tick: int, reason: str) -> bool:
        if reason not in ("discovered", "recovered", "transferred", "dropped"):
            raise ValueError("Unknown artifact movement")
        request = {"kind": "artifact_move", "artifact_id": artifact_id, "tick": tick, "reason": reason,
                   "new_owner": owner.to_dict() if owner else None, "new_holder": holder.to_dict()}
        self._validate_tick(tick)
        if self._already_applied(operation_id, request):
            return False
        current = self.artifacts[artifact_id]
        self.artifacts[artifact_id] = replace(current, owner=owner, custodian=holder,
                                              history=(*current.history, operation_id))
        self.operations[operation_id] = {**request, "event_id": None}
        return True

    def consume_ward(self, holder: AssetRef, *, operation_id: str, tick: int) -> str | None:
        self._validate_tick(tick)
        if operation_id in self.operations:
            raise ValueError("Ward consumption must not be replayed as a new injury")
        available = sorted(item.artifact_id for item in self.artifacts.values()
                           if item.kind == "ancient_relic" and item.custodian == holder and item.charges > 0)
        if not available:
            return None
        item = self.artifacts[available[0]]
        self.artifacts[item.artifact_id] = replace(
            item, charges=item.charges - 1, history=(*item.history, operation_id),
        )
        self.operations[operation_id] = {"kind": "ward_used", "artifact_id": item.artifact_id,
                                         "holder": holder.to_dict(), "tick": tick, "event_id": None}
        return item.artifact_id

    def drop_carried(self, holder: AssetRef, site: AssetRef, *, operation_id: str, tick: int) -> list[str]:
        """Move custody, preserving ownership. A casualty's possessions are not destroyed."""
        if site.kind != "site":
            raise ValueError("Dropped assets require a site")
        operations = []
        for item in sorted(self.artifacts.values(), key=lambda value: value.artifact_id):
            if item.custodian == holder:
                op = f"{operation_id}:artifact:{item.artifact_id}"
                self.move_artifact(item.artifact_id, item.owner, site, operation_id=op, tick=tick, reason="dropped")
                operations.append(op)
        for index, ((resource, owner, custodian), quantity) in enumerate(sorted(self.stocks.items())):
            if custodian == holder:
                op = f"{operation_id}:stock:{index}"
                self.transfer_stock(resource, owner, holder, owner, site, quantity, operation_id=op, tick=tick)
                operations.append(op)
        return operations

    def bind_event(self, operation_ids: list[str], event_id: str) -> None:
        identifier(event_id, "asset event")
        for key in operation_ids:
            operation = self.operations[key]
            if operation.get("event_id") not in (None, event_id):
                raise ValueError("Asset operation already belongs to another event")
            operation["event_id"] = event_id

    @staticmethod
    def _validate_tick(tick: int) -> None:
        if type(tick) is not int or tick < 0:
            raise ValueError("Asset operation requires a nonnegative tick")

    def to_dict(self) -> dict[str, Any]:
        from .persistence import validate_ledger
        validate_ledger(self)
        return {"stocks": [{"resource": key[0], "owner": key[1].to_dict(), "holder": key[2].to_dict(),
                            "quantity": quantity} for key, quantity in sorted(self.stocks.items())],
                "artifacts": [item.to_dict() for _, item in sorted(self.artifacts.items())],
                "seeded_sites": sorted(self.seeded_sites), "operations": deepcopy(self.operations)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetLedger":
        from .persistence import hydrate_ledger
        return hydrate_ledger(cls(), data)
