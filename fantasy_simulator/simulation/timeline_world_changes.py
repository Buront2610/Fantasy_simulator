"""Natural world-change phase for the simulation timeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .calendar import distributed_budget
from .timeline_pipeline import DayPhaseContext
from .world_change_driver import generate_world_change

if TYPE_CHECKING:
    from ..world import World


class TimelineWorldChangeMixin:
    if TYPE_CHECKING:
        world: World
        world_changes_per_year: int
        pending_notifications: list[Any]
        rng: Any

        def should_notify(self, record: Any) -> bool: ...

    def _world_changes_for_day(self, month: int, day: int) -> int:
        """Number of natural world changes to generate on this in-world day."""
        del month, day
        return distributed_budget(
            self.world_changes_per_year,
            self.world.days_per_year,
            self.rng,
        )

    def _run_world_change_phase(self, day_context: DayPhaseContext) -> None:
        """Generate natural PR-K world changes after ordinary character events."""
        for _ in range(self._world_changes_for_day(day_context.month, day_context.day)):
            record = generate_world_change(
                self.world,
                month=day_context.month,
                day=day_context.day,
                rng=self.rng,
            )
            if record is not None and self.should_notify(record):
                self.pending_notifications.append(record)
