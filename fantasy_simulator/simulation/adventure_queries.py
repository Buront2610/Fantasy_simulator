"""Adventure read-model and choice-resolution helpers for the simulator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from ..adventure.itinerary import AdventureItinerary

if TYPE_CHECKING:
    from ..world import World

from ..adventure import AdventureRun
from ..adventure.roles import ROLE_SKILLS, capability
from ..i18n import tr
from .adventure_transition import apply_adventure_transition


class AdventureQueryMixin:
    """Mixin for player-facing adventure queries and choice APIs."""

    if TYPE_CHECKING:
        world: World
        elapsed_days: int
        _format_party_names_from_list: Callable[[List[str]], str]

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
        details = list(run.detail_log)
        if run.objective is not None:
            goal = run.objective
            target = self.world.get_character_by_id(goal.target_id) if goal.target_id else None
            details.append(tr("adventure.objective_status", purpose=tr(f"adventure.purpose_{goal.purpose}"),
                              pace=tr(f"adventure.pace_{goal.pace}"), status=tr(f"adventure.goal_{goal.status}"),
                              target=target.name if target else tr("adventure.no_target"),
                              retreat=tr(f"adventure.retreat_{run.retreat_rule}")))
        if run.objective is not None and not run.is_resolved:
            details.extend(self._adventure_role_details(run))
        if run.schedule is not None and not run.is_resolved:
            tick = self.elapsed_days + 1
            details.append(tr(
                "adventure.schedule_status", days=max(0, run.schedule.next_step_tick - tick),
                provisions=run.schedule.remaining_provisions(tick, len(run.member_ids)),
                deadline=max(0, run.schedule.deadline_tick - tick),
            ))
        if run.itinerary is not None:
            details.append(self._adventure_position_text(run.itinerary))
        return details

    def _adventure_position_text(self, itinerary: AdventureItinerary) -> str:
        if itinerary.active_leg is not None:
            assert itinerary.arrival_tick is not None
            return tr("adventure.in_transit",
                      origin=self.world.location_name(itinerary.current_site_id),
                      destination=self.world.location_name(itinerary.active_leg.destination),
                      days=max(0, itinerary.arrival_tick - self.elapsed_days - 1))
        key = "adventure.route_waiting" if itinerary.waiting_for_route else "adventure.at_site"
        return tr(key, location=self.world.location_name(itinerary.current_site_id))

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
                        "option_effects": {
                            option: tr(f"adventure.effect_{option}") for option in run.pending_choice.options
                        } if run.schedule is not None else {},
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
        if char is None or not char.alive:
            return False
        apply_adventure_transition(self, run, choice=True, option=option)
        return True

    def _adventure_role_details(self, run: AdventureRun) -> List[str]:
        members = run._party_members(self.world)
        lines = []
        for role in ROLE_SKILLS:
            current = capability(members, role)
            actor = self.world.get_character_by_id(current.holder_id) if current.holder_id else None
            lines.append(tr("adventure.role_status", role=tr(f"adventure.role_{role}"),
                            name=actor.name if actor else tr("adventure.role_unfilled"), score=round(current.score, 1),
                            effect=tr(f"adventure.role_effect_{role}")))
        return lines
