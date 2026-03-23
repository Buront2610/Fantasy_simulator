"""Adventure lifecycle management for the Simulator.

Handles adventure creation, step-by-step progression, dead-character
resolution, and player-facing query methods.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..adventure import AdventureRun, create_adventure_run
from ..i18n import tr


class AdventureMixin:
    """Mixin providing adventure management methods for the Simulator.

    Expected attributes on *self* (provided by ``engine.Simulator``):
    - ``world``: the World instance
    - ``current_month``: current in-world month (1–12)
    - ``adventure_steps_per_year``: steps to advance per year
    - ``event_system``: EventSystem instance
    - ``rng``, ``id_rng``: RNG instances
    - ``_recently_completed_adventures``: list of recently completed runs
    """

    def _maybe_start_adventure(self) -> None:
        """Start at most one new adventure in the current year."""
        candidates = [
            c for c in self.world.characters
            if c.alive and c.active_adventure_id is None
            and c.injury_status not in ("injured", "serious", "dying")
        ]
        if not candidates or self.rng.random() >= 0.25:
            return

        char = self.rng.choice(candidates)
        run = create_adventure_run(char, self.world, rng=self.rng, id_rng=self.id_rng)
        char.active_adventure_id = run.adventure_id
        char.add_history(
            tr(
                "set_out_for_adventure",
                year=self.world.year,
                origin=self.world.location_name(run.origin),
                destination=self.world.location_name(run.destination),
            )
        )
        self.world.add_adventure(run)
        self._record_world_event(
            run.summary_log[-1],
            kind="adventure_started",
            location_id=run.origin,
            primary_actor_id=char.char_id,
            severity=2,
        )

    def _advance_adventures(self) -> None:
        """Advance active adventures by multiple internal steps per year."""
        paused_until_next_year = set()
        for _ in range(self.adventure_steps_per_year):
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
                previous_state = run.state
                summaries = run.step(char, self.world, rng=self.rng)
                for entry in summaries:
                    kind, location_id, severity = self._classify_adventure_summary(previous_state, run)
                    self._record_world_event(
                        entry,
                        kind=kind,
                        location_id=location_id,
                        primary_actor_id=run.character_id,
                        severity=severity,
                    )
                if not char.alive:
                    self.event_system.handle_death_side_effects(char, self.world)
                if run.is_resolved:
                    self._recently_completed_adventures.append(run)
                    self.world.complete_adventure(run.adventure_id)
                elif not had_pending_choice and run.pending_choice is not None:
                    paused_until_next_year.add(run.adventure_id)

    def _resolve_dead_character_adventure(self, run: AdventureRun, char) -> None:
        run.pending_choice = None
        run.state = "resolved"
        run.outcome = "death"
        run.resolution_year = self.world.year
        char.active_adventure_id = None
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
        self.event_system.handle_death_side_effects(char, self.world)
        self._recently_completed_adventures.append(run)
        self.world.complete_adventure(run.adventure_id)

    def get_adventure_summaries(self, include_active: bool = True) -> List[str]:
        """Return summary lines for known adventures."""
        runs = list(self.world.completed_adventures)
        if include_active:
            runs.extend(self.world.active_adventures)
        summaries: List[str] = []
        for run in runs:
            status_key = f"outcome_{run.outcome}" if run.outcome else f"state_{run.state}"
            status = tr(status_key)
            origin_name = self.world.location_name(run.origin)
            dest_name = self.world.location_name(run.destination)
            summaries.append(
                f"{run.character_name}: {origin_name} -> {dest_name} [{status}]"
            )
        return summaries

    def get_adventure_details(self, adventure_id: str) -> List[str]:
        """Return detailed log entries for a specific adventure."""
        run = self.world.get_adventure_by_id(adventure_id)
        if run is None:
            return []
        return list(run.detail_log)

    def get_pending_adventure_choices(self) -> List[Dict[str, Any]]:
        """Return all unresolved adventure choices."""
        pending: List[Dict[str, Any]] = []
        for run in self.world.active_adventures:
            if run.pending_choice is not None:
                pending.append(
                    {
                        "adventure_id": run.adventure_id,
                        "character_id": run.character_id,
                        "character_name": run.character_name,
                        "prompt": run.pending_choice.prompt,
                        "options": list(run.pending_choice.options),
                        "default_option": run.pending_choice.default_option,
                    }
                )
        return pending

    def resolve_adventure_choice(
        self,
        adventure_id: str,
        option: Optional[str] = None,
    ) -> bool:
        """Resolve a pending choice on a specific adventure."""
        run = self.world.get_adventure_by_id(adventure_id)
        if run is None or run.pending_choice is None:
            return False
        char = self.world.get_character_by_id(run.character_id)
        if char is None:
            return False
        summaries = run.resolve_choice(self.world, char, option=option)
        for entry in summaries:
            self._record_world_event(
                entry,
                kind="adventure_choice",
                month=self.current_month,
                location_id=run.destination,
                primary_actor_id=run.character_id,
            )
        return True
