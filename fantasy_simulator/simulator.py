"""
simulator.py - Orchestrates the world simulation loop.
"""

from __future__ import annotations

import random
import ast
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .adventure import AdventureRun, create_adventure_run
from .events import EventResult, EventSystem, WorldEventRecord, generate_record_id
from .i18n import get_locale, set_locale, tr, tr_term
from .reports import (
    format_monthly_report,
    format_yearly_report,
    generate_monthly_report,
    generate_yearly_report,
)
from .rumor import age_rumors, generate_rumors_for_period, trim_rumors

if TYPE_CHECKING:
    from .character import Character
    from .world import World


class Simulator:
    """Drives the world simulation forward in time.

    Parameters
    ----------
    world : World
        The World instance to simulate.
    events_per_year : int
        How many random events to generate each in-world year.
    seed : Optional[int]
        If provided, seeds the random number generator for reproducibility.
    """

    def __init__(
        self,
        world: World,
        events_per_year: int = 8,
        adventure_steps_per_year: int = 3,
        seed: Optional[int] = None,
    ) -> None:
        self.world = world
        self.events_per_year = events_per_year
        self.adventure_steps_per_year = adventure_steps_per_year
        self.event_system = EventSystem()
        # Compatibility cache of EventResult objects for legacy summaries,
        # filters, and save/load paths. The canonical structured history lives
        # in world.event_records.
        self.history: List[EventResult] = []
        # Mutable progress marker for structured event timestamps within the
        # current simulated year. This value is serialized and restored as-is
        # to preserve in-progress context across save/load.
        self.current_month: int = 1
        # Baseline year used for "latest completed report year" fallback when
        # the simulation has not yet completed a full year.
        self.start_year: int = world.year
        self.rng = random.Random(seed)
        self.id_rng = random.Random(self._id_seed_from_seed(seed))
        # Events that passed the should_notify() threshold during the
        # most recent advance_years() call, available for the UI layer.
        self.pending_notifications: List[WorldEventRecord] = []
        # Adventures completed during the current year, used by
        # _check_pause_conditions() for the party_returned condition.
        self._recently_completed_adventures: List[AdventureRun] = []
        # Favorites whose condition worsened this year, used for
        # event-based condition_worsened_favorite pause checks.
        self._favorites_worsened_this_year: set[str] = set()
        # Accumulated seasonal delta tuples for _revert_seasonal_modifiers()
        self._active_seasonal_deltas: List[tuple] = []

    # Severity scale: 1=minor, 2=notable, 3=significant, 4=major, 5=critical
    _SEVERITY_MAP: Dict[str, int] = {
        "death": 5, "battle_fatal": 5, "marriage": 4,
        "discovery": 3, "battle": 3, "journey": 2,
        "meeting": 1, "aging": 1, "skill_training": 1,
        "romance": 2, "anniversary": 2,
        "condition_worsened": 3, "dying_rescued": 4,
    }

    # Internal event-generation density multiplier (§B-1).
    # Scales how many random events are generated per simulated month.
    # SIMULATION_DENSITY=1.0 preserves the events_per_year target.
    # Higher values produce denser internal history; the notification
    # thresholds (NOTIFICATION_THRESHOLDS) keep the player-visible
    # signal-to-noise ratio stable regardless of this setting.
    SIMULATION_DENSITY: float = 1.0

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

    # Seasonal modifiers applied to locations each year (design §5.7).
    # Mapped to actual region_types: city, village, forest, dungeon, mountain, plains, sea.
    SEASONAL_MODIFIERS: Dict[tuple, Dict[str, int]] = {
        # Winter: mountains & forests become treacherous, sea routes close
        ("winter", "mountain"): {"danger": +30, "road_condition": -20},
        ("winter", "forest"): {"danger": +15, "road_condition": -15},
        ("winter", "sea"): {"traffic": -20},
        ("winter", "plains"): {"road_condition": -10},
        # Spring: settlements brighten, forests become safer
        ("spring", "village"): {"mood": +10, "traffic": +10},
        ("spring", "city"): {"mood": +5, "traffic": +10},
        ("spring", "forest"): {"danger": -10},
        # Summer: cities & sea routes thrive, plains easy to traverse
        ("summer", "city"): {"traffic": +20},
        ("summer", "sea"): {"traffic": +20, "danger": -10},
        ("summer", "plains"): {"traffic": +15},
        # Autumn: wilds grow dangerous, dungeons more active
        ("autumn", "plains"): {"danger": +10},
        ("autumn", "forest"): {"danger": +10},
        ("autumn", "dungeon"): {"danger": +15},
    }

    # --- Notification density configuration (§8 of implementation_plan) ---
    # These thresholds control what gets surfaced to the player vs what
    # stays as internal simulation detail.
    NOTIFICATION_THRESHOLDS: Dict[str, Any] = {
        "favorite_any": True,          # any event involving a favorite is notified
        "spotlight_serious": True,     # spotlighted char: severity >= 3
        "rumor_high_heat": 70,         # rumor_heat >= 70 triggers location notification
    }

    @staticmethod
    def _id_seed_from_seed(seed: Optional[int]) -> int:
        base_seed = 0 if seed is None else seed
        return base_seed ^ 0x5EED5EED

    @staticmethod
    def _legacy_id_seed(data: Dict[str, Any]) -> int:
        world_data = data.get("world", {})
        seed = world_data.get("year", 0)
        for count in (
            len(data.get("history", [])),
            len(world_data.get("event_records", [])),
            len(world_data.get("active_adventures", [])),
            len(world_data.get("completed_adventures", [])),
        ):
            seed = (seed * 1_000_003 + count) & ((1 << 64) - 1)
        return seed ^ 0x5EED5EED

    @staticmethod
    def _restore_rng_state(rng: random.Random, state_repr: Optional[str]) -> bool:
        if state_repr is None:
            return False
        try:
            parsed = ast.literal_eval(state_repr)
            if (
                isinstance(parsed, tuple)
                and len(parsed) == 3
                and isinstance(parsed[0], int)
                and isinstance(parsed[1], tuple)
            ):
                rng.setstate(parsed)
                return True
        except (ValueError, SyntaxError, TypeError):
            return False
        return False

    def _record_world_event(
        self,
        description: str,
        *,
        kind: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
        location_id: Optional[str] = None,
        primary_actor_id: Optional[str] = None,
        secondary_actor_ids: Optional[List[str]] = None,
        severity: int = 1,
        visibility: str = "public",
    ) -> WorldEventRecord:
        """Record a structured world event and mirror it to the legacy text log."""
        self.world.log_event(description)
        record = WorldEventRecord(
            record_id=generate_record_id(self.id_rng),
            kind=kind,
            year=self.world.year if year is None else year,
            month=self.current_month if month is None else month,
            location_id=location_id,
            primary_actor_id=primary_actor_id,
            secondary_actor_ids=[] if secondary_actor_ids is None else list(secondary_actor_ids),
            description=description,
            severity=severity,
            visibility=visibility,
        )
        self.world.record_event(record)
        # Apply event impact on location state (design §5.5)
        self.world.apply_event_impact(kind, location_id)
        # Surface notable events to the UI layer via notification thresholds
        if self.should_notify(record):
            self.pending_notifications.append(record)
        return record

    def _link_relation_tag_source_from_record(self, result: EventResult, record_id: str) -> None:
        """Attach canonical WorldEventRecord IDs to relation tag sources."""
        updates = result.metadata.get("relation_tag_updates", [])
        for update in updates:
            source_id = update.get("source")
            target_id = update.get("target")
            tag = update.get("tag")
            if not source_id or not target_id or not tag:
                continue
            source_char = self.world.get_character_by_id(source_id)
            if source_char is None or not source_char.has_relation_tag(target_id, tag):
                continue
            source_char.add_relation_tag(target_id, tag, source_event_id=record_id)

    @staticmethod
    def _classify_adventure_summary(previous_state: str, run: AdventureRun) -> tuple[str, str, int]:
        if previous_state == "traveling":
            return "adventure_arrived", run.destination, 2
        if previous_state == "waiting_for_choice":
            return "adventure_choice", run.destination, 1
        if previous_state == "exploring":
            if run.outcome == "death":
                return "adventure_death", run.destination, 5
            if run.state == "returning" and run.injury_status != "none":
                return "adventure_injured", run.destination, 3
            return "adventure_discovery", run.destination, 2
        if previous_state == "returning":
            if run.outcome == "injury":
                return "adventure_returned_injured", run.origin, 3
            if run.outcome == "safe_return":
                return "adventure_returned", run.origin, 2
            if run.outcome == "retreat":
                return "adventure_retreated", run.origin, 1
        return "adventure_update", run.destination, 1

    def _record_event(self, result: EventResult, location_id: Optional[str] = None) -> None:
        """Mirror an EventResult into all transitional event stores.

        During the Phase 1 -> Phase 2 migration:
        - history keeps the legacy EventResult view alive
        - world.event_log keeps CLI-facing formatted strings alive
        - world.event_records is the canonical structured event history
        """
        self.history.append(result)
        severity = self._SEVERITY_MAP.get(result.event_type, 1)
        record = self._record_world_event(
            result.description,
            kind=result.event_type,
            year=result.year,
            location_id=location_id,
            primary_actor_id=result.affected_characters[0] if result.affected_characters else None,
            secondary_actor_ids=result.affected_characters[1:],
            severity=severity,
        )
        self._link_relation_tag_source_from_record(result, record.record_id)

    # ------------------------------------------------------------------
    # Main simulation loop
    # ------------------------------------------------------------------

    def run(self, years: int = 10) -> None:
        """Simulate *years* years of in-world history.

        Each year:
        1. Check for natural deaths.
        2. Generate *events_per_year* random events.
        3. Advance the world clock.
        """
        self.advance_years(years)

    def advance_years(self, years: int = 1) -> None:
        """Advance the simulation by a public number of whole years."""
        self.pending_notifications.clear()
        for _ in range(years):
            self._run_year()

    def advance_months(self, months: int = 1) -> None:
        """Advance the simulation by *months* in-world months.

        Handles year-end transitions automatically: when month 12 completes,
        world.advance_time(1) is called and per-year tracking sets are cleared,
        then processing continues with month 1 of the next year.

        Unlike advance_years(), this method respects the current position within
        the year so partial-year advancement is supported.
        """
        self.pending_notifications.clear()
        for _ in range(months):
            self._run_month(self.current_month)
            if self.current_month == 12:
                self.world.advance_time(1)
                self._recently_completed_adventures.clear()
                self._favorites_worsened_this_year.clear()
            self.current_month = (self.current_month % 12) + 1

    def advance_until_pause(self, max_years: int = 12) -> Dict[str, Any]:
        """Advance the simulation until a pause condition triggers or max_years.

        Returns a dict with 'years_advanced', 'pause_reason', and 'pause_priority'.
        This implements the conditional auto-advance system (design §4.4).
        """
        self.pending_notifications.clear()
        # These are "recent year" markers and should not trigger
        # repeated 0-year pauses across separate auto-advance requests.
        self._favorites_worsened_this_year.clear()
        self._recently_completed_adventures.clear()
        preexisting_reason = self._check_pause_conditions()
        if preexisting_reason is not None:
            return {
                "years_advanced": 0,
                "pause_reason": preexisting_reason,
                "pause_priority": self.AUTO_PAUSE_PRIORITIES.get(preexisting_reason, 0),
            }
        years_advanced = 0
        for _ in range(max_years):
            self._run_year()
            years_advanced += 1
            reason = self._check_pause_conditions()
            if reason is not None:
                return {
                    "years_advanced": years_advanced,
                    "pause_reason": reason,
                    "pause_priority": self.AUTO_PAUSE_PRIORITIES.get(reason, 0),
                }
        return {
            "years_advanced": years_advanced,
            "pause_reason": "years_elapsed",
            "pause_priority": self.AUTO_PAUSE_PRIORITIES["years_elapsed"],
        }

    def _check_pause_conditions(self) -> Optional[str]:
        """Check if any auto-pause condition is met. Returns highest-priority reason."""
        reasons: List[tuple] = []

        for char in self.world.characters:
            if not char.alive:
                continue
            if char.is_dying:
                if char.spotlighted:
                    reasons.append(("dying_spotlighted",
                                    self.AUTO_PAUSE_PRIORITIES["dying_spotlighted"]))
                elif char.favorite:
                    reasons.append(("dying_favorite",
                                    self.AUTO_PAUSE_PRIORITIES["dying_favorite"]))
                else:
                    reasons.append(("dying_any",
                                    self.AUTO_PAUSE_PRIORITIES["dying_any"]))
            if char.favorite and char.char_id in self._favorites_worsened_this_year:
                reasons.append(("condition_worsened_favorite",
                                self.AUTO_PAUSE_PRIORITIES["condition_worsened_favorite"]))

        # Pending adventure choices
        for run in self.world.active_adventures:
            if run.pending_choice is not None:
                reasons.append(("pending_decision",
                                self.AUTO_PAUSE_PRIORITIES["pending_decision"]))
                break

        # Party returned (design §4.4: check recently completed adventures)
        if self._recently_completed_adventures:
            for run in self._recently_completed_adventures:
                char = self.world.get_character_by_id(run.character_id)
                if char and (char.favorite or char.spotlighted):
                    reasons.append(("party_returned",
                                    self.AUTO_PAUSE_PRIORITIES["party_returned"]))
                    break

        if not reasons:
            return None
        reasons.sort(key=lambda x: -x[1])
        return reasons[0][0]

    def _run_year(self) -> None:
        """Process a full year by running each month in strict chronological order.

        Delegates all per-month logic to _run_month() so that events are always
        timestamped to the month in which they actually occur.  This replaces
        the old single-pass approach where random events received arbitrary
        month labels and all processing collapsed into one undifferentiated year.
        """
        # Reset per-year tracking for pause conditions
        self._recently_completed_adventures.clear()
        self._favorites_worsened_this_year.clear()

        for month in range(1, 13):
            self._run_month(month)

        self.world.advance_time(1)
        # Reset so that current_month reflects the start of the next year.
        # advance_months() already applies this reset via its modular counter;
        # keeping them consistent avoids divergence in serialised snapshots.
        self.current_month = 1

    def _events_for_month(self, month: int) -> int:
        """Number of random events to generate this month.

        Distributes ``events_per_year * SIMULATION_DENSITY`` evenly across
        12 months.  When the per-month quota has a fractional part, the
        remainder is resolved probabilistically so the *expected* yearly
        total equals ``events_per_year * SIMULATION_DENSITY`` exactly.

        :param month: current in-world month (1–12); reserved for future
            month-weight variations (e.g. more events in summer).
        """
        total = self.events_per_year * self.SIMULATION_DENSITY
        base = int(total / 12)
        remainder = total / 12 - base
        # Guard against floating-point noise (e.g. 0.9999... instead of 1.0)
        # so that a mathematically zero remainder never triggers an extra roll.
        _FLOAT_EPS = 1e-9
        extra = 1 if (remainder > _FLOAT_EPS and self.rng.random() < remainder) else 0
        return base + extra

    def _run_month(self, month: int) -> None:
        """Process a single in-world month in strict chronological order.

        All events recorded inside this method are timestamped to *month*.
        Seasonal modifiers are applied at entry and reverted on exit (even on
        exception) via a try/finally guard.

        Per-month processing order:

        1.  Seasonal modifiers applied (all months).
        2.  Dying resolution, natural-death checks, injury recovery (month 1).
        3.  Rumor aging — once per year at month 1.
        4.  Adventure start and full-year progression (month 2).
        5.  Random events distributed by ``SIMULATION_DENSITY`` (all months).
        6.  Rumor generation from this month's events (all months).
        7.  State propagation and rumor trim (month 12).
        8.  Seasonal modifiers reverted (all months, via finally).
        """
        self.current_month = month
        self._apply_seasonal_modifiers(month)
        try:
            # --- Year-opening events (month 1) ---
            if month == 1:
                self._resolve_dying_characters()
                for char in list(self.world.characters):
                    result = self.event_system.check_natural_death(
                        char, self.world, rng=self.rng
                    )
                    if result is not None:
                        if result.event_type == "condition_worsened" and char.favorite:
                            self._favorites_worsened_this_year.add(char.char_id)
                        self._record_event(result, location_id=char.location_id)
                self._recover_injuries()
                # Age existing rumors once per year at year-start
                active, expired = age_rumors(self.world.rumors, months=12)
                self.world.rumors = active
                self.world.rumor_archive.extend(expired)

            # --- Adventure start and progression (month 2, spring) ---
            if month == 2:
                self._maybe_start_adventure()
                self._advance_adventures()

            # --- Random events distributed by SIMULATION_DENSITY ---
            for _ in range(self._events_for_month(month)):
                result = self.event_system.generate_random_event(
                    self.world.characters, self.world, rng=self.rng
                )
                if result is None:
                    break
                primary_id = result.affected_characters[0] if result.affected_characters else None
                primary_char = self.world.get_character_by_id(primary_id) if primary_id else None
                loc_id = primary_char.location_id if primary_char else None
                self._record_event(result, location_id=loc_id)

            # --- Rumor generation from this month's events ---
            new_rumors = generate_rumors_for_period(
                self.world, year=self.world.year, month=month, max_rumors=3, rng=self.rng,
            )
            self.world.rumors.extend(new_rumors)

            # --- Year-end processing (month 12) ---
            if month == 12:
                self.world.propagate_state()
                kept, trimmed = trim_rumors(self.world.rumors)
                self.world.rumors = kept
                self.world.rumor_archive.extend(trimmed)
        finally:
            self._revert_seasonal_modifiers()

    def _resolve_dying_characters(self) -> None:
        """Give dying characters a chance at rescue or death (design §8.3)."""
        for char in list(self.world.characters):
            if not char.alive or char.injury_status != "dying":
                continue
            result = self.event_system.check_dying_resolution(
                char, self.world, rng=self.rng
            )
            if result is not None:
                self._record_event(result, location_id=char.location_id)

    def _recover_injuries(self) -> None:
        """Give injured/serious characters a chance to recover during normal life.

        Recovery is staged (design §8): serious→injured (30%), injured→none (50%).
        Dying characters are handled separately in _resolve_dying_characters.
        """
        for char in self.world.characters:
            if not char.alive or char.injury_status not in ("injured", "serious"):
                continue
            # Serious: 30% chance to recover to injured
            if char.injury_status == "serious":
                if self.rng.random() < 0.3:
                    char.injury_status = "injured"
                    message = tr("condition_improved", name=char.name,
                                 status=tr("injury_status_injured"))
                    char.add_history(tr("history_condition_improved", year=self.world.year,
                                        status=tr("injury_status_injured")))
                    self._record_world_event(
                        message,
                        kind="injury_recovery",
                        location_id=char.location_id,
                        primary_actor_id=char.char_id,
                    )
                continue
            # Injured: 50% chance to recover to none
            if self.rng.random() < 0.5:
                char.injury_status = "none"
                message = tr("recovered_from_injuries", name=char.name)
                char.add_history(tr("history_recovered_from_injuries", year=self.world.year))
                self._record_world_event(
                    message,
                    kind="injury_recovery",
                    location_id=char.location_id,
                    primary_actor_id=char.char_id,
                )

    def _apply_seasonal_modifiers(self, month: int) -> None:
        """Apply seasonal modifiers to locations based on current month (design §5.7).

        Modifiers are temporary adjustments applied before events/adventures
        and reversed after, so they influence outcomes without permanently
        drifting location stats.
        """
        season = self.world.get_season(month)
        self._active_seasonal_deltas: List[tuple] = []
        for (s, region), deltas in self.SEASONAL_MODIFIERS.items():
            if s != season:
                continue
            for loc in self.world.grid.values():
                if loc.region_type != region:
                    continue
                for attr, delta in deltas.items():
                    if not hasattr(loc, attr):
                        continue
                    old_val = getattr(loc, attr)
                    new_val = max(0, min(100, old_val + delta))
                    setattr(loc, attr, new_val)
                    self._active_seasonal_deltas.append((loc, attr, new_val - old_val))

    def _revert_seasonal_modifiers(self) -> None:
        """Revert seasonal modifiers applied by _apply_seasonal_modifiers."""
        for loc, attr, applied_delta in self._active_seasonal_deltas:
            old_val = getattr(loc, attr)
            setattr(loc, attr, max(0, min(100, old_val - applied_delta)))
        self._active_seasonal_deltas.clear()

    def _generate_and_age_rumors(self) -> None:
        """Perform the full annual rumor cycle as a single batch operation.

        .. deprecated::
            The per-month rumor cycle is now handled incrementally inside
            ``_run_month()``: aging at month 1, generation each month, and
            trim at month 12.  This method is kept for callers that need to
            apply the full yearly cycle in one shot (e.g. external tooling or
            legacy tests); it is no longer called from ``_run_year()``.
        """
        # Age existing rumors once at year start
        active, expired = age_rumors(self.world.rumors, months=12)
        self.world.rumors = active
        self.world.rumor_archive.extend(expired)

        # Generate rumors for each month of the year
        for gen_month in range(1, 13):
            new_rumors = generate_rumors_for_period(
                self.world,
                year=self.world.year,
                month=gen_month,
                max_rumors=3,
                rng=self.rng,
            )
            self.world.rumors.extend(new_rumors)

        kept, trimmed = trim_rumors(self.world.rumors)
        self.world.rumors = kept
        self.world.rumor_archive.extend(trimmed)

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

    def _resolve_dead_character_adventure(self, run: AdventureRun, char: Character) -> None:
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

    # ------------------------------------------------------------------
    # Summary & stories
    # ------------------------------------------------------------------

    def get_summary(self) -> str:
        """Return a human-readable summary using WorldEventRecord as canonical source."""
        records = self.world.event_records
        total = len(records)
        alive = sum(1 for c in self.world.characters if c.alive)
        dead = sum(1 for c in self.world.characters if not c.alive)

        type_counts: Dict[str, int] = {}
        for rec in records:
            type_counts[rec.kind] = type_counts.get(rec.kind, 0) + 1

        lines = [
            "=" * 60,
            f"  {tr('summary_title', world=self.world.name)}",
            f"  {tr('final_year')}: {self.world.year}",
            "=" * 60,
            f"  {tr('total_events'):<22}: {total}",
            f"  {tr('characters_alive'):<22}: {alive}",
            f"  {tr('characters_deceased'):<22}: {dead}",
            "",
            f"  {tr('event_breakdown')}:",
        ]
        for etype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            i18n_key = f"event_type_{etype}"
            localized_type = tr(i18n_key)
            # Fallback: if tr() returned the key unchanged, show the raw kind
            if localized_type == i18n_key:
                localized_type = etype.replace("_", " ").capitalize()
            lines.append(f"    {localized_type:<20} {count:>4} {tr('times_suffix')}")

        lines.append("")
        lines.append(f"  {tr('notable_moments')}:")
        dramatic = [
            rec for rec in records
            if rec.kind in ("marriage", "battle_fatal", "death", "discovery")
        ]
        shown = dramatic[:5] if len(dramatic) >= 5 else dramatic
        for rec in shown:
            lines.append(f"    • {rec.description}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def get_monthly_report(self, year: int, month: int) -> str:
        """Generate and format a monthly report for the given year and month."""
        report = generate_monthly_report(self.world, year, month)
        return format_monthly_report(report)

    def get_yearly_report(self, year: int) -> str:
        """Generate and format a yearly report for the given year."""
        report = generate_yearly_report(self.world, year)
        return format_yearly_report(report)

    def get_latest_completed_report_year(self) -> int:
        """Return the latest year that should be used for end-of-year reports.

        Preference is "last completed year" (`world.year - 1`). If the
        simulation has not completed even one full year yet, this falls back
        to the simulator baseline (`start_year`). If historical event records
        from earlier years exist (e.g. imported data), that earlier year is
        also respected as a valid lower bound.
        """
        candidate = self.world.year - 1
        baseline = self.start_year
        if self.world.event_records:
            baseline = min(baseline, min(r.year for r in self.world.event_records))
        return max(candidate, baseline)

    def get_latest_yearly_report(self) -> str:
        """Generate and format a yearly report for the most recent completed year."""
        return self.get_yearly_report(self.get_latest_completed_report_year())

    def should_notify(self, record: WorldEventRecord) -> bool:
        """Determine if an event record should trigger a player notification.

        Applies notification density thresholds (§8 of implementation plan)
        to separate internal simulation events from player-visible alerts.
        """
        thresholds = self.NOTIFICATION_THRESHOLDS

        # Always notify for major events (severity >= 4)
        if record.severity >= 4:
            return True

        # Check favorite characters
        if thresholds.get("favorite_any"):
            for char in self.world.characters:
                if not char.favorite:
                    continue
                if (record.primary_actor_id == char.char_id
                        or char.char_id in record.secondary_actor_ids):
                    return True

        # Check spotlighted characters (severity >= 3)
        if thresholds.get("spotlight_serious"):
            for char in self.world.characters:
                if not char.spotlighted:
                    continue
                if record.severity >= 3 and (
                    record.primary_actor_id == char.char_id
                    or char.char_id in record.secondary_actor_ids
                ):
                    return True

        # Check location rumor_heat threshold
        heat_threshold = thresholds.get("rumor_high_heat", 0)
        if heat_threshold and record.location_id:
            loc = self.world.get_location_by_id(record.location_id)
            if loc is not None and loc.rumor_heat >= heat_threshold:
                return True

        return False

    def get_active_rumors(self) -> List[str]:
        """Return formatted strings for currently active rumors."""
        lines: List[str] = []
        for rumor in self.world.rumors:
            if rumor.is_expired:
                continue
            reliability_label = tr(f"rumor_reliability_{rumor.reliability}")
            lines.append(f"{rumor.description} ({reliability_label})")
        return lines

    def get_character_story(self, char_id: str) -> str:
        """Return the life story of a single character.

        Parameters
        ----------
        char_id : str
            The character's unique ID.
        """
        char = self.world.get_character_by_id(char_id)
        if char is None:
            return tr("no_character_found", char_id=char_id)

        lines = [
            "─" * 50,
            f"  {tr('story_of', name=char.name)}",
            f"  {tr_term(char.race)} {tr_term(char.job)}",
            "─" * 50,
        ]
        if char.history:
            for entry in char.history:
                lines.append(f"  • {entry}")
        else:
            lines.append(f"  {tr('no_notable_events')}")

        lines.append("")
        lines.append(char.stat_block())
        lines.append("─" * 50)
        return "\n".join(lines)

    def get_all_stories(self, only_alive: bool = False) -> str:
        """Return stories for all characters, optionally filtering to the living."""
        chars = self.world.characters
        if only_alive:
            chars = [c for c in chars if c.alive]
        return "\n\n".join(self.get_character_story(c.char_id) for c in chars)

    # ------------------------------------------------------------------
    # Event log access
    # ------------------------------------------------------------------

    def get_event_log(self, last_n: Optional[int] = None) -> List[str]:
        """Return the compatibility text log, optionally only the last *n*."""
        log = self.world.event_log
        if last_n is not None:
            return log[-last_n:]
        return log

    def events_by_type(self, event_type: str) -> List[EventResult]:
        """Return legacy EventResult entries of the given type."""
        return [ev for ev in self.history if ev.event_type == event_type]

    def to_dict(self) -> Dict[str, Any]:
        """Serialise simulator state, including compatibility history."""
        return {
            "world": self.world.to_dict(),
            "characters": [char.to_dict() for char in self.world.characters],
            "events_per_year": self.events_per_year,
            "adventure_steps_per_year": self.adventure_steps_per_year,
            "current_month": self.current_month,
            "start_year": self.start_year,
            "locale": get_locale(),
            "rng_state": repr(self.rng.getstate()),
            "id_rng_state": repr(self.id_rng.getstate()),
            "history": [ev.to_dict() for ev in self.history],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Simulator":
        """Rebuild a simulator from a serialised snapshot."""
        from .character import Character
        from .world import World

        world = World.from_dict(data["world"])
        characters = [
            Character.from_dict(char_data) for char_data in data.get("characters", [])
        ]
        world.characters = characters
        world.normalize_after_load()
        sim = cls(
            world,
            events_per_year=data.get("events_per_year", 8),
            adventure_steps_per_year=data.get("adventure_steps_per_year", 3),
        )
        set_locale(data.get("locale", get_locale()))
        sim._restore_rng_state(sim.rng, data.get("rng_state"))
        if not sim._restore_rng_state(sim.id_rng, data.get("id_rng_state")):
            sim.id_rng.seed(sim._legacy_id_seed(data))
        sim.current_month = max(1, min(12, data.get("current_month", 1)))
        sim.start_year = data.get("start_year", sim.world.year)
        sim.history = [
            EventResult.from_dict(ev) for ev in data.get("history", [])
        ]
        return sim

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
