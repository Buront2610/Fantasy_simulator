"""Inventory views query one registry, rather than reconstructing loot from prose."""

from typing import Any

from ..assets.models import AssetRef
from ..i18n import tr


def _holder_name(world: Any, ref: AssetRef | None) -> str:
    if ref is None:
        return tr("assets.unowned")
    if ref.kind == "site":
        return world.location_name(ref.reference_id)
    actor = world.get_character_by_id(ref.reference_id)
    return actor.name if actor else ref.reference_id


def _position(world: Any, holder: AssetRef) -> str:
    if holder.kind == "site":
        return world.location_name(holder.reference_id)
    actor = world.get_character_by_id(holder.reference_id)
    if actor is None:
        return tr("assets.unknown_position")
    if not actor.alive:
        return tr("assets.last_known", location=world.location_name(actor.location_id))
    site = world.character_presence_location_id(actor)
    return world.location_name(site) if site else tr("assets.in_transit")


def asset_lines(world: Any, subject: AssetRef) -> list[str]:
    lines = []
    for (resource, owner, holder), quantity in sorted(world.assets.stocks.items()):
        if subject in (owner, holder):
            lines.append(tr("assets.stock_line", resource=tr(f"assets.kind_{resource}"), quantity=quantity,
                            owner=_holder_name(world, owner), holder=_holder_name(world, holder),
                            location=_position(world, holder)))
    for _, item in sorted(world.assets.artifacts.items()):
        if subject in (item.owner, item.custodian):
            lines.append(tr("assets.artifact_line", name=tr(f"assets.kind_{item.kind}"), identifier=item.artifact_id,
                            owner=_holder_name(world, item.owner), holder=_holder_name(world, item.custodian),
                            location=_position(world, item.custodian), charges=item.charges))
            if item.inscription:
                lines.append(tr("assets.inscription", text=item.inscription))
    return lines
