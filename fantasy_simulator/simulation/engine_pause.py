"""Conditional auto-advance pause handling for :class:`~.engine.Simulator`."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..adventure import AdventureRun


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
        "years_elapsed": 10,
    }

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
        return {
            "days_advanced": days_advanced,
            "months_advanced": months_advanced,
            "years_advanced": years_advanced,
            "pause_reason": pause_reason,
            "pause_priority": self.AUTO_PAUSE_PRIORITIES.get(pause_reason, 0),
            "supplemental_reasons": supplemental_reasons,
            "pause_context": self._pause_context_for_reason(pause_reason),
        }

    def _check_pause_conditions(self) -> Optional[str]:
        """Check if any auto-pause condition is met. Returns highest-priority reason."""
        reasons = self._collect_pause_conditions()
        if not reasons:
            return None
        return reasons[0]

    def _collect_pause_conditions(self) -> List[str]:
        """Return pause reasons sorted by priority (highest first)."""
        reasons: List[tuple] = []

        for char in self.world.characters:
            if not char.alive:
                continue
            if char.is_dying:
                if char.spotlighted:
                    reasons.append(("dying_spotlighted", self.AUTO_PAUSE_PRIORITIES["dying_spotlighted"]))
                elif char.favorite:
                    reasons.append(("dying_favorite", self.AUTO_PAUSE_PRIORITIES["dying_favorite"]))
                else:
                    reasons.append(("dying_any", self.AUTO_PAUSE_PRIORITIES["dying_any"]))
            if char.favorite and char.char_id in self._favorites_worsened_this_year:
                reasons.append((
                    "condition_worsened_favorite",
                    self.AUTO_PAUSE_PRIORITIES["condition_worsened_favorite"],
                ))

        for run in self.world.active_adventures:
            if run.pending_choice is not None:
                reasons.append(("pending_decision", self.AUTO_PAUSE_PRIORITIES["pending_decision"]))
                break

        if self._recently_completed_adventures:
            for run in self._recently_completed_adventures:
                char = self._watched_party_member(run)
                if char is not None:
                    reasons.append(("party_returned", self.AUTO_PAUSE_PRIORITIES["party_returned"]))
                    break

        reasons.sort(key=lambda x: -x[1])
        return [reason for reason, _ in reasons]

    def _pause_context_for_reason(self, reason: str) -> Dict[str, str]:
        """Return lightweight context (character/location) for a pause reason."""
        if reason.startswith("dying"):
            for char in self.world.characters:
                if char.alive and char.is_dying:
                    return {"character": char.name, "location": self.world.location_name(char.location_id)}
        if reason == "pending_decision":
            for run in self.world.active_adventures:
                if run.pending_choice is not None:
                    return {"character": run.character_name, "location": self.world.location_name(run.destination)}
        if reason == "party_returned" and self._recently_completed_adventures:
            for run in reversed(self._recently_completed_adventures):
                watched = self._watched_party_member(run)
                if watched is not None:
                    return {"character": watched.name, "location": self.world.location_name(run.origin)}
            run = self._recently_completed_adventures[-1]
            return {"character": run.character_name, "location": self.world.location_name(run.origin)}
        return {}

    def _watched_party_member(self, run: AdventureRun):
        """Return a watched member of the run, if one exists."""
        member_ids = list(run.member_ids) or [run.character_id]
        for member_id in member_ids:
            char = self.world.get_character_by_id(member_id)
            if char is not None and (char.favorite or char.spotlighted or char.playable):
                return char
        return None
