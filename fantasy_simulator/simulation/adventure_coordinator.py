"""Adventure lifecycle management for the Simulator.

This module keeps the active adventure progression loop and composes helper
mixins for launch, memory, and query responsibilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..adventure import AdventureRun, AdventureStepResult, select_party_policy
from ..i18n import tr
from ..adventure.results import step_fact_result
from .adventure_memory import AdventureMemoryMixin
from .adventure_partying import AdventureStartMixin
from .adventure_queries import AdventureQueryMixin

if TYPE_CHECKING:
    from ..character import Character

__all__ = ["AdventureMixin", "select_party_policy"]


class AdventureMixin(
    AdventureStartMixin,
    AdventureMemoryMixin,
    AdventureQueryMixin,
):
    """Mixin providing adventure management methods for the Simulator.

    Expected attributes on *self* (provided by ``engine.Simulator``):
    - ``world``: the World instance
    - ``current_month``: current in-world month (1–12)
    - ``adventure_steps_per_year``: steps to advance per year
    - ``event_system``: EventSystem instance
    - ``rng``, ``id_rng``: RNG instances
    - ``_recently_completed_adventures``: list of recently completed runs
    """

    def _advance_adventures(self, steps: Optional[int] = None) -> None:
        """Advance active adventures by a configurable number of internal steps."""
        paused_until_next_year = set()
        step_budget = self.adventure_steps_per_year if steps is None else max(0, steps)
        for _ in range(step_budget):
            active_ids = [run.adventure_id for run in self.world.active_adventures]
            for adventure_id in active_ids:
                if adventure_id in paused_until_next_year:
                    continue
                run = self.world.get_adventure_by_id(adventure_id)
                if run is None or run.is_resolved:
                    continue
                char = self.world.get_character_by_id(run.character_id)
                if char is None:
                    continue
                if not char.alive:
                    self._resolve_dead_character_adventure(run, char)
                    continue
                had_pending_choice = run.pending_choice is not None
                result = run.step_result(char, self.world, rng=self.rng)
                self._record_adventure_step_result(run, result)
                if not char.alive:
                    self.event_system.handle_death_side_effects(char, self.world)
                if run.is_resolved:
                    self._complete_resolved_adventure(run)
                elif not had_pending_choice and run.pending_choice is not None:
                    paused_until_next_year.add(run.adventure_id)

    def _record_adventure_step_result(self, run: AdventureRun, result: AdventureStepResult) -> None:
        """Store facts as emitted; translated prose never determines their kind."""
        if result.adventure_id != run.adventure_id:
            raise ValueError("Adventure result belongs to another run")
        for fact in result.facts:
            record = self._record_world_event(
                fact.description, kind=fact.kind, location_id=fact.location_id,
                primary_actor_id=fact.primary_actor_id, secondary_actor_ids=list(fact.secondary_actor_ids),
                cause_event_ids=list(fact.cause_event_ids), severity=fact.severity,
                summary_key=fact.summary_key, render_params=fact.render_params,
            )
            run.related_event_ids.append(record.record_id)

    def _complete_resolved_adventure(self, run: AdventureRun) -> None:
        """Apply side effects and move a resolved adventure into completed storage."""
        if run.outcome == "death":
            deceased = self.world.get_character_by_id(run.death_member_id or run.character_id)
            if deceased is not None and not deceased.alive:
                self.event_system.handle_death_side_effects(deceased, self.world)
        self._apply_world_memory(run)
        self._recently_completed_adventures.append(run)
        self.world.complete_adventure(run.adventure_id)

    def _resolve_dead_character_adventure(self, run: AdventureRun, char: "Character") -> None:
        run.pending_choice = None
        run.state = "resolved"
        run.outcome = "death"
        run.death_member_id = char.char_id
        run.resolution_year = self.world.year
        run._clear_member_adventures(self.world)
        char.add_history(
            tr(
                "history_adventure_detail",
                year=self.world.year,
                detail=tr(
                    "detail_adventure_died", name=char.name,
                    destination=self.world.location_name(run.destination),
                ),
            )
        )
        self._record_adventure_step_result(run, step_fact_result(
            run, "adventure_death", "summary_adventure_died",
            {"name": char.name, "destination": self.world.location_name(run.destination)},
            actor_id=char.char_id, severity=5,
        ))
        self._complete_resolved_adventure(run)
