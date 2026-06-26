"""Conditional auto-advance pause handling for :class:`~.engine.Simulator`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..adventure import AdventureRun
from ..world_event.models import WorldEventRecord
from ..world_event.index import location_ids_for_record

if TYPE_CHECKING:
    from ..world import World


@dataclass(frozen=True)
class _PauseCandidate:
    reason: str
    priority: int
    context: Dict[str, str]


def _pause_candidate(reason: str, priority: int, context: Dict[str, str]) -> _PauseCandidate:
    return _PauseCandidate(reason=reason, priority=priority, context=context)


def _pause_recommendations_for_reason_context(reason: str, context: Dict[str, str]) -> List[Dict[str, str]]:
    character = context.get("character", "")
    location = context.get("location", "")
    character_id = context.get("character_id", "")
    location_id = context.get("location_id", "")
    base = {
        "character_id": character_id,
        "character": character,
        "location_id": location_id,
        "location": location,
        "record_id": context.get("record_id", ""),
        "event_kind": context.get("event_kind", ""),
        "target_type": context.get("target_type", ""),
        "target_id": context.get("target_id", ""),
    }
    if reason.startswith("dying") or reason == "condition_worsened_favorite":
        actions = [{"key": "inspect_character", **base}]
        if location:
            actions.append({"key": "inspect_location", **base})
        return actions
    action_by_reason = {
        "pending_decision": "review_pending_adventure",
        "party_returned": "review_party_returned",
        "world_change_notification": "review_world_dashboard",
        "years_elapsed": "review_recent_events",
    }
    action_key = action_by_reason.get(reason)
    if action_key is None:
        return []
    return [{"key": action_key, **base}]


def _pause_subreasons_for_reason_context(reason: str, context: Dict[str, str]) -> List[Dict[str, str]]:
    payload = {
        "character_id": context.get("character_id", ""),
        "character": context.get("character", ""),
        "location_id": context.get("location_id", ""),
        "location": context.get("location", ""),
        "record_id": context.get("record_id", ""),
        "event_kind": context.get("event_kind", ""),
        "target_type": context.get("target_type", ""),
        "target_id": context.get("target_id", ""),
    }
    if reason.startswith("dying"):
        return [{"key": "actor_in_danger", **payload}]
    key_by_reason = {
        "condition_worsened_favorite": "watched_condition_worsened",
        "pending_decision": "adventure_needs_decision",
        "party_returned": "watched_party_returned",
        "world_change_notification": "world_change_notification",
        "years_elapsed": "auto_window_elapsed",
    }
    subreason_key = key_by_reason.get(reason)
    if subreason_key is None:
        return []
    return [{"key": subreason_key, **payload}]


class EnginePauseMixin:
    """Evaluate and report conditional auto-pause state."""

    # Conditional auto-advance pause priorities (design §4.5)
    AUTO_PAUSE_PRIORITIES: Dict[str, int] = {
        "dying_spotlighted": 100,
        "pending_decision": 90,
        "dying_favorite": 80,
        "party_returned": 70,
        "dying_any": 60,
        "condition_worsened_favorite": 50,
        "world_change_notification": 40,
        "years_elapsed": 10,
    }

    if TYPE_CHECKING:
        world: World
        pending_notifications: List[WorldEventRecord]
        _favorites_worsened_this_year: set[str]
        _recently_completed_adventures: List[AdventureRun]
        current_month: int
        current_day: int
        elapsed_days: int

        def _reset_yearly_trackers(self) -> None: ...

        def _run_day(self, month: int, day: int) -> None: ...

    def advance_until_pause(self, max_years: int = 12) -> Dict[str, Any]:
        """Advance the simulation day-by-day until a pause condition triggers.

        Returns a dict with 'days_advanced', 'months_advanced', 'years_advanced',
        'pause_reason', and 'pause_priority'. The daily granularity allows pause
        conditions to fire without waiting for a month or year boundary.

        This implements the conditional auto-advance system (design §4.4).
        """
        self.pending_notifications.clear()
        self._favorites_worsened_this_year.clear()
        self._recently_completed_adventures.clear()
        preexisting_reason = self._check_pause_conditions()
        if preexisting_reason is not None:
            all_reasons = self._collect_pause_conditions()
            return self._pause_result(
                days_advanced=0,
                months_advanced=0,
                years_advanced=0,
                pause_reason=preexisting_reason,
                supplemental_reasons=[r for r in all_reasons if r != preexisting_reason],
            )
        max_days = max_years * self.world.days_per_year
        days_advanced = 0
        months_advanced = 0
        years_advanced = 0
        for _ in range(max_days):
            if self.current_month == 1 and self.current_day == 1:
                self._reset_yearly_trackers()
            previous_month = self.current_month
            self._run_day(self.current_month, self.current_day)
            self.current_month, self.current_day, year_delta = self.world.advance_calendar_position(
                self.current_month,
                self.current_day,
                days=1,
            )
            self.elapsed_days += 1
            if year_delta:
                self.world.advance_time(year_delta)
                years_advanced += year_delta
            if self.current_day == 1 and self.current_month != previous_month:
                months_advanced += 1
            days_advanced += 1
            reason = self._check_pause_conditions()
            if reason is not None:
                all_reasons = self._collect_pause_conditions()
                return self._pause_result(
                    days_advanced=days_advanced,
                    months_advanced=months_advanced,
                    years_advanced=years_advanced,
                    pause_reason=reason,
                    supplemental_reasons=[r for r in all_reasons if r != reason],
                )
        return self._pause_result(
            days_advanced=days_advanced,
            months_advanced=months_advanced,
            years_advanced=years_advanced,
            pause_reason="years_elapsed",
            supplemental_reasons=[],
        )

    def _pause_result(
        self,
        *,
        days_advanced: int,
        months_advanced: int,
        years_advanced: int,
        pause_reason: str,
        supplemental_reasons: List[str],
    ) -> Dict[str, Any]:
        """Build the public auto-pause result payload."""
        recommended_actions = self._pause_recommendations_for_reasons(
            pause_reason,
            supplemental_reasons,
        )
        return {
            "days_advanced": days_advanced,
            "months_advanced": months_advanced,
            "years_advanced": years_advanced,
            "pause_reason": pause_reason,
            "pause_priority": self.AUTO_PAUSE_PRIORITIES.get(pause_reason, 0),
            "pause_subreasons": self._pause_subreasons_for_reason(pause_reason),
            "supplemental_reasons": supplemental_reasons,
            "pause_context": self._pause_context_for_reason(pause_reason),
            "recommended_actions": recommended_actions,
        }

    def _check_pause_conditions(self) -> Optional[str]:
        """Check if any auto-pause condition is met. Returns highest-priority reason."""
        candidates = self._collect_pause_candidates()
        if not candidates:
            return None
        return candidates[0].reason

    def _collect_pause_conditions(self) -> List[str]:
        """Return pause reasons sorted by priority (highest first)."""
        return [candidate.reason for candidate in self._collect_pause_candidates()]

    def _collect_pause_candidates(self) -> List[_PauseCandidate]:
        """Return pause candidates sorted by priority (highest first)."""
        candidates: List[_PauseCandidate] = []
        for char in self.world.characters:
            if not char.alive:
                continue
            if char.is_dying:
                if char.spotlighted:
                    candidates.append(self._pause_candidate_for_character_reason("dying_spotlighted", char))
                elif char.favorite:
                    candidates.append(self._pause_candidate_for_character_reason("dying_favorite", char))
                else:
                    candidates.append(self._pause_candidate_for_character_reason("dying_any", char))
            if char.favorite and char.char_id in self._favorites_worsened_this_year:
                candidates.append(self._pause_candidate_for_character_reason("condition_worsened_favorite", char))

        for run in self.world.active_adventures:
            if run.pending_choice is not None:
                candidates.append(_pause_candidate(
                    "pending_decision",
                    self.AUTO_PAUSE_PRIORITIES["pending_decision"],
                    self._pause_context_for_adventure(run, location_id=run.destination),
                ))
                break

        if self._recently_completed_adventures:
            for run in reversed(self._recently_completed_adventures):
                char = self._watched_party_member(run)
                if char is not None:
                    candidates.append(_pause_candidate(
                        reason="party_returned",
                        priority=self.AUTO_PAUSE_PRIORITIES["party_returned"],
                        context={
                            "character_id": char.char_id,
                            "character": char.name,
                            "location_id": run.origin,
                            "location": self.world.location_name(run.origin),
                        },
                    ))
                    break

        world_change_notification = self._latest_world_change_notification()
        if world_change_notification is not None:
            candidates.append(_pause_candidate(
                reason="world_change_notification",
                priority=self.AUTO_PAUSE_PRIORITIES["world_change_notification"],
                context=self._pause_context_for_world_change(world_change_notification),
            ))

        candidates.sort(key=lambda candidate: -candidate.priority)
        return candidates

    def _pause_candidate_for_character_reason(self, reason: str, char) -> _PauseCandidate:
        return _pause_candidate(
            reason=reason,
            priority=self.AUTO_PAUSE_PRIORITIES[reason],
            context=self._pause_context_for_character(char),
        )

    def _pause_context_for_character(self, char) -> Dict[str, str]:
        return {
            "character_id": char.char_id,
            "character": char.name,
            "location_id": char.location_id,
            "location": self.world.location_name(char.location_id),
        }

    def _pause_context_for_adventure(self, run: AdventureRun, *, location_id: str) -> Dict[str, str]:
        return {
            "character_id": run.character_id,
            "character": run.character_name,
            "location_id": location_id,
            "location": self.world.location_name(location_id),
        }

    def _latest_world_change_notification(self):
        for record in reversed(self.pending_notifications):
            if "world_change" in record.tags:
                return record
        return None

    def _world_change_target_context(self, record) -> Dict[str, str]:
        for impact in getattr(record, "impacts", []):
            target_type = str(impact.get("target_type", "")).strip()
            target_id = str(impact.get("target_id", "")).strip()
            if target_type and target_id:
                return {"target_type": target_type, "target_id": target_id}

        target_fields = (
            ("route", "route_id"),
            ("location", "location_id"),
            ("terrain_cell", "terrain_cell_id"),
            ("era", "new_era_key"),
            ("civilization", "new_phase"),
        )
        for target_type, field_name in target_fields:
            target_id = str(record.render_params.get(field_name, "")).strip()
            if target_id:
                return {"target_type": target_type, "target_id": target_id}
        return {"target_type": "", "target_id": ""}

    def _pause_context_for_world_change(self, record) -> Dict[str, str]:
        location_ids = location_ids_for_record(record)
        location_id = location_ids[0] if location_ids else ""
        location = self.world.location_name(location_id) if location_id else ""
        return {
            "character_id": "",
            "character": "",
            "location_id": location_id,
            "location": location,
            "record_id": record.record_id,
            "event_kind": record.kind,
            **self._world_change_target_context(record),
        }

    def _pause_context_for_reason(self, reason: str) -> Dict[str, str]:
        """Return lightweight context (character/location) for a pause reason."""
        for candidate in self._collect_pause_candidates():
            if candidate.reason == reason:
                return dict(candidate.context)
        return {}

    def _pause_recommendations_for_reasons(
        self,
        pause_reason: str,
        supplemental_reasons: List[str],
    ) -> List[Dict[str, str]]:
        """Return concise follow-up checks for the pause result."""
        recommendations: List[Dict[str, str]] = []
        for reason in [pause_reason, *supplemental_reasons]:
            recommendations.extend(self._pause_recommendations_for_reason(reason))

        deduped: List[Dict[str, str]] = []
        seen = set()
        for item in recommendations:
            key = (
                item.get("key", ""),
                item.get("character_id", item.get("character", "")),
                item.get("location_id", item.get("location", "")),
                item.get("record_id", ""),
                item.get("target_type", ""),
                item.get("target_id", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped[:3]

    def _pause_recommendations_for_reason(self, reason: str) -> List[Dict[str, str]]:
        """Map an auto-pause reason to player-facing follow-up actions."""
        return _pause_recommendations_for_reason_context(reason, self._pause_context_for_reason(reason))

    def _pause_subreasons_for_reason(self, reason: str) -> List[Dict[str, str]]:
        """Return explanatory details for the primary pause reason."""
        return _pause_subreasons_for_reason_context(reason, self._pause_context_for_reason(reason))

    def _watched_party_member(self, run: AdventureRun):
        """Return a watched member of the run, if one exists."""
        member_ids = list(run.member_ids) or [run.character_id]
        for member_id in member_ids:
            char = self.world.get_character_by_id(member_id)
            if char is not None and (char.favorite or char.spotlighted or char.playable):
                return char
        return None
