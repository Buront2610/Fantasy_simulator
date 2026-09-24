"""Concrete expedition goals, independent of pace and retreat rules."""

from dataclasses import asdict, dataclass

from .schedule import PACE_DURATION
from .cargo_model import CargoLoad


@dataclass
class AdventureObjective:
    purpose: str = "explore"
    pace: str = "standard"
    target_id: str | None = None
    source_adventure_id: str | None = None
    evidence_event_id: str | None = None
    status: str = "active"
    reason: str | None = None
    cargo: CargoLoad | None = None

    def validate(self) -> None:
        if self.purpose not in ("explore", "rescue", "transport") or self.pace not in PACE_DURATION:
            raise ValueError("Unknown adventure purpose or pace")
        if self.status not in ("active", "rescued", "completed", "failed", "invalidated"):
            raise ValueError("Unknown objective status")
        for value in (self.target_id, self.source_adventure_id, self.evidence_event_id, self.reason):
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError("Objective references must be nonempty strings")
        if (self.purpose == "rescue") != (self.target_id is not None):
            raise ValueError("Rescue requires a real target; exploration has no target")
        if (self.purpose == "transport") != (self.cargo is not None):
            raise ValueError("Transport requires a real cargo manifest")
        if self.cargo is not None:
            self.cargo.validate()
            if (self.status == "completed") != (self.cargo.state == "delivered"):
                raise ValueError("Transport completion requires delivery")
            if self.cargo.state in ("returned", "stranded") and self.status != "failed":
                raise ValueError("An undelivered closed shipment must have a failed objective")

    def to_dict(self) -> dict:
        result = asdict(self)
        if self.cargo is None:
            result.pop("cargo")
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "AdventureObjective":
        data = dict(data)
        if data.get("cargo") is not None:
            data["cargo"] = CargoLoad(**data["cargo"])
        result = cls(**data)
        result.validate()
        return result


def default_objective(policy: str) -> AdventureObjective:
    """New exploration does not invent a target for an old rescue-style policy."""
    pace = {"cautious": "cautious", "swift": "swift", "rescue": "cautious"}.get(policy, "standard")
    return AdventureObjective(pace=pace)
