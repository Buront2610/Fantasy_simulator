"""Serializable cargo manifest, separate from transport execution."""

from dataclasses import dataclass

from ..assets.models import RESOURCES

CARGO_CAPACITY = 10


@dataclass
class CargoLoad:
    resource: str
    quantity: int
    source_kind: str = "character"
    state: str = "planned"

    def validate(self) -> None:
        if self.resource not in RESOURCES or type(self.quantity) is not int or not 1 <= self.quantity <= CARGO_CAPACITY:
            raise ValueError("Cargo requires a known resource and a quantity within carrier capacity")
        if self.source_kind not in ("character", "site"):
            raise ValueError("Unknown cargo source")
        if self.state not in ("planned", "in_transit", "delivered", "returned", "stranded"):
            raise ValueError("Unknown cargo state")
