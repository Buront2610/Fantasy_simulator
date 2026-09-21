"""Persisted per-adventure timing and supplies, measured in simulation days."""

from dataclasses import asdict, dataclass
from math import ceil


PACE_DURATION = {"standard": 1.0, "cautious": 1.5, "swift": 0.75}
PACE_RISK = {"standard": 1.0, "cautious": 0.70, "swift": 1.20}
PACE_DISCOVERY = {"standard": 1.0, "cautious": 1.10, "swift": 0.90}


@dataclass
class AdventureSchedule:
    next_step_tick: int
    last_tick: int
    interval_days: int
    deadline_tick: int
    provisions: int
    initial_provisions: int
    segment_mode: str = "standard"

    def __post_init__(self) -> None:
        for name in ("next_step_tick", "last_tick", "interval_days", "deadline_tick",
                     "provisions", "initial_provisions"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.interval_days < 1 or self.initial_provisions < 1:
            raise ValueError("Adventure duration and initial provisions must be positive")
        if self.next_step_tick < self.last_tick or self.provisions > self.initial_provisions:
            raise ValueError("Inconsistent adventure schedule")
        if self.segment_mode not in PACE_DURATION:
            raise ValueError("Unknown adventure segment mode")

    @classmethod
    def begin(cls, tick: int, interval: int, members: int) -> "AdventureSchedule":
        provisions = interval * 6 * members
        return cls(tick + interval, tick, interval, tick + interval * 6, provisions, provisions)

    def remaining_provisions(self, tick: int, members: int) -> int:
        return max(0, self.provisions - max(0, tick - self.last_tick) * members)

    def settle(self, tick: int, members: int) -> None:
        if tick < self.last_tick:
            raise ValueError("Adventure clock cannot move backwards")
        self.provisions = self.remaining_provisions(tick, members)
        self.last_tick = tick

    def plan_next(self, state: str, tick: int) -> None:
        duration = 1 if state == "waiting_for_choice" else self.interval_days
        if state == "exploring":
            duration = max(1, ceil(duration * PACE_DURATION[self.segment_mode]))
        self.next_step_tick = tick + duration
        if state not in ("returning", "resolved"):
            self.next_step_tick = min(self.next_step_tick, max(tick + 1, self.deadline_tick))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AdventureSchedule":
        return cls(**data)
