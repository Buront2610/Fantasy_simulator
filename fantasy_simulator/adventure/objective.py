"""Concrete expedition goals, independent of pace and retreat rules."""

from dataclasses import asdict, dataclass

from .schedule import PACE_DURATION


@dataclass
class AdventureObjective:
    purpose: str = "explore"
    pace: str = "standard"
    target_id: str | None = None
    source_adventure_id: str | None = None
    evidence_event_id: str | None = None
    status: str = "active"
    reason: str | None = None

    def validate(self) -> None:
        if self.purpose not in ("explore", "rescue") or self.pace not in PACE_DURATION:
            raise ValueError("Unknown adventure purpose or pace")
        if self.status not in ("active", "rescued", "completed", "failed", "invalidated"):
            raise ValueError("Unknown objective status")
        for value in (self.target_id, self.source_adventure_id, self.evidence_event_id, self.reason):
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError("Objective references must be nonempty strings")
        if (self.purpose == "rescue") != (self.target_id is not None):
            raise ValueError("Rescue requires a real target; exploration has no target")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AdventureObjective":
        result = cls(**data)
        result.validate()
        return result


def default_objective(policy: str) -> AdventureObjective:
    """New exploration does not invent a target for an old rescue-style policy."""
    pace = {"cautious": "cautious", "swift": "swift", "rescue": "cautious"}.get(policy, "standard")
    return AdventureObjective(pace=pace)
