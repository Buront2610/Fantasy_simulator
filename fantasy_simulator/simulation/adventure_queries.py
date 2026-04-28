"""Adventure read-model and choice-resolution helpers for the simulator."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..adventure import AdventureRun
from ..i18n import tr


class AdventureQueryMixin:
    """Mixin for player-facing adventure queries and choice APIs."""

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
            if run.is_party:
                party_names = self._build_party_display_names(run)
                summaries.append(
                    f"{party_names}: {origin_name} -> {dest_name} [{status}]"
                )
            else:
                summaries.append(
                    f"{run.character_name}: {origin_name} -> {dest_name} [{status}]"
                )
        return summaries

    def _build_party_display_names(self, run: AdventureRun) -> str:
        """Return display names for party members, falling back to leader name."""
        names = []
        for mid in run.member_ids:
            c = self.world.get_character_by_id(mid)
            if c is not None:
                names.append(c.name)
        if not names:
            names = [run.character_name]
        return self._format_party_names_from_list(names)

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
