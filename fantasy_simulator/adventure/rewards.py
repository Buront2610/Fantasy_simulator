"""Concrete discoveries and consumable ward effects on the closed adventure draft."""

from dataclasses import dataclass, field
from typing import Any

from ..assets.models import AssetRef
from .constants import ADVENTURE_DISCOVERIES

LABELS = {"ancient_relic": "an ancient relic", "moon_silver": "a pouch of moon-silver",
          "lore_fragment": "a fragment of lost lore", "monster_trophy": "a cache of monster trophies"}


@dataclass(frozen=True)
class DiscoveryReward:
    label: str
    details: dict[str, Any] = field(default_factory=dict)


def find_discovery(world: Any, run: Any, members: list[Any], rng: Any) -> DiscoveryReward | None:
    if run.objective is None:
        return DiscoveryReward(rng.choice(ADVENTURE_DISCOVERIES))
    ledger, site = world.assets, AssetRef("site", run.destination)
    ledger.seed_site(run.destination)
    artifact_candidates, stock_candidates, available = _site_candidates(ledger, site)
    if not available:
        return None
    kind = rng.choice(available)
    recipients = sorted((member for member in members if member.alive), key=lambda member: member.char_id)
    if not recipients:
        raise ValueError("A discovery needs a living carrier")
    operation = f"discover:{run.adventure_id}:{run.steps_taken}"
    details: dict[str, Any]
    if kind in ("ancient_relic", "lore_fragment"):
        item = next(item for item in artifact_candidates if item.kind == kind)
        recipient = AssetRef("character", recipients[run.steps_taken % len(recipients)].char_id)
        ledger.move_artifact(item.artifact_id, item.owner or recipient, recipient, operation_id=operation,
                             tick=world.tick, reason="recovered" if item.owner else "discovered")
        details = {"asset_operations": [operation], "artifact_ids": [item.artifact_id]}
    else:
        source = next(key for key in stock_candidates if key[0] == kind)
        details = _divide_stock(ledger, source, recipients, operation, world.tick)
    cache_op = f"cache:{run.destination}"
    if ledger.operations[cache_op].get("event_id") is None:
        details["asset_operations"].insert(0, cache_op)
    return DiscoveryReward(LABELS[kind], details)


def _site_candidates(ledger: Any, site: AssetRef) -> tuple[list[Any], list[Any], list[str]]:
    artifacts = sorted((item for item in ledger.artifacts.values() if item.custodian == site),
                       key=lambda item: item.artifact_id)
    stocks = sorted(key for key in ledger.stocks if key[2] == site)
    present_kinds = {item.kind for item in artifacts} | {key[0] for key in stocks}
    return artifacts, stocks, [kind for kind in LABELS if kind in present_kinds]


def _divide_stock(ledger: Any, source: Any, recipients: list[Any], operation: str, tick: int) -> dict[str, Any]:
    resource, owner, site = source
    total = min(10 if resource == "moon_silver" else 3, ledger.stocks[source])
    quotient, remainder = divmod(total, len(recipients))
    shares, operations = {}, []
    for index, member in enumerate(recipients):
        amount = quotient + (index < remainder)
        if not amount:
            continue
        recipient = AssetRef("character", member.char_id)
        op = f"{operation}:{member.char_id}"
        ledger.transfer_stock(resource, owner, site, recipient if owner == site else owner, recipient, amount,
                              operation_id=op, tick=tick)
        shares[member.char_id] = amount
        operations.append(op)
    return {"asset_operations": operations, "resource": resource, "resource_shares": shares}


def ward_injury(world: Any, run: Any, character: Any, severity: int) -> tuple[int, dict[str, Any]]:
    if run.objective is None or severity <= 0:
        return severity, {}
    op = f"ward:{run.adventure_id}:{run.steps_taken}"
    artifact_id = world.assets.consume_ward(AssetRef("character", character.char_id), operation_id=op, tick=world.tick)
    if artifact_id is None:
        return severity, {}
    return severity - 1, {"ward_artifact_id": artifact_id, "ward_prevented_steps": 1, "asset_operations": [op]}


def drop_casualty_assets(world: Any, run: Any, character: Any, severity: int) -> list[str]:
    if run.objective is None or severity < 2:
        return []
    return world.assets.drop_carried(
        AssetRef("character", character.char_id), AssetRef("site", run.itinerary.current_site_id),
        operation_id=f"casualty:{run.adventure_id}:{run.steps_taken}", tick=world.tick,
    )
