"""Explicit player-requested shipment of an owner's existing resources."""

from typing import Any

from ..adventure import AdventureRun, generate_adventure_id
from ..adventure.cargo_model import CargoLoad
from ..adventure.objective import AdventureObjective
from ..i18n import tr
from .adventure_transaction import restore_start_rng_on_failure


@restore_start_rng_on_failure
def start_transport(sim: Any, carrier_id: str, destination: str, resource: str, quantity: int,
                    *, source_kind: str = "character") -> AdventureRun:
    carrier = sim.world.get_character_by_id(carrier_id)
    location = sim.world.get_location_by_id(destination)
    if carrier is None or location is None:
        raise ValueError("Unknown carrier or delivery destination")
    cargo = CargoLoad(resource, quantity, source_kind)
    cargo.validate()
    summary = tr("cargo.departure", name=carrier.name, resource=tr(f"assets.kind_{resource}"),
                 quantity=quantity, destination=sim.world.location_name(destination))
    run = AdventureRun(carrier.char_id, carrier.name, carrier.location_id, destination, sim.world.year,
                       adventure_id=generate_adventure_id(sim.id_rng), danger_level=location.danger,
                       objective=AdventureObjective(purpose="transport", cargo=cargo), summary_log=[summary])
    sim._commit_adventure_start(run, [carrier])
    return run
