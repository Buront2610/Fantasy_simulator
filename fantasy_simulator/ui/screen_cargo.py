"""Request physical transport of resources owned by the selected carrier."""

from typing import Any

from ..adventure.cargo_model import CARGO_CAPACITY
from ..assets.models import AssetRef
from ..i18n import tr
from ..simulation.cargo_dispatch import start_transport
from .screen_input import _get_numeric_choice
from .ui_context import UIContext


def _cargo_options(world: Any) -> list[tuple[Any, str, str, int]]:
    options = []
    for (resource, owner, holder), quantity in sorted(world.assets.stocks.items()):
        if owner.kind != "character":
            continue
        carrier = world.get_character_by_id(owner.reference_id)
        if carrier is None or not carrier.alive or carrier.injury_status != "none" or carrier.active_adventure_id:
            continue
        if holder not in (owner, AssetRef("site", carrier.location_id)):
            continue
        options.append((carrier, resource, holder.kind, min(quantity, CARGO_CAPACITY)))
    return options


def request_cargo_transport(sim: Any, ctx: UIContext) -> bool:
    options = _cargo_options(sim.world)
    if not options:
        ctx.out.print_dim(tr("cargo.no_stock"))
        ctx.inp.pause()
        return False
    for index, (carrier, resource, kind, quantity) in enumerate(options, 1):
        label = tr("cargo.option", name=carrier.name, resource=tr(f"assets.kind_{resource}"), quantity=quantity,
                   source=tr(f"cargo.source_{kind}"))
        ctx.out.print_line(f"{index}. {label}")
    choice = _get_numeric_choice(tr("cargo.choose_load"), len(options), ctx=ctx)
    if choice is None:
        return False
    carrier, resource, source_kind, available = options[choice]
    destinations = sorted(site for site in sim.world.reachable_location_ids(carrier.location_id)
                          if site != carrier.location_id)
    for index, site in enumerate(destinations, 1):
        ctx.out.print_line(f"{index}. {sim.world.location_name(site)}")
    destination = _get_numeric_choice(tr("cargo.choose_destination"), len(destinations), ctx=ctx)
    if destination is None:
        return False
    raw = ctx.inp.read_line(tr("cargo.quantity", maximum=available)).strip()
    if not raw.isdecimal() or not 1 <= int(raw) <= available:
        ctx.out.print_warning(tr("invalid_input"))
        return False
    try:
        run = start_transport(sim, carrier.char_id, destinations[destination], resource, int(raw),
                              source_kind=source_kind)
    except ValueError:
        ctx.out.print_warning(tr("cargo.unavailable"))
        return False
    ctx.out.print_line(run.summary_log[-1])
    ctx.inp.pause()
    return True
