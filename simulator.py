"""
simulator.py - Orchestrates the world simulation loop.
"""

from __future__ import annotations

import random
import ast
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from adventure import AdventureRun, create_adventure_run
from events import EventResult, EventSystem, WorldEventRecord, generate_record_id
from i18n import get_locale, set_locale, tr, tr_term
from reports import (
    format_monthly_report,
    format_yearly_report,
    generate_monthly_report,
    generate_yearly_report,
)

if TYPE_CHECKING:
    from character import Character
    from world import World


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
        self.current_month: int = 0
        self.rng = random.Random(seed)
        self.id_rng = random.Random(self._id_seed_from_seed(seed))

    # Severity scale: 1=minor, 2=notable, 3=significant, 4=major, 5=critical
    _SEVERITY_MAP: Dict[str, int] = {
        "death": 5, "battle_fatal": 5, "marriage": 4,
        "discovery": 3, "battle": 3, "journey": 2,
        "meeting": 1, "aging": 1, "skill_training": 1,
        "romance": 2, "anniversary": 2,
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
    ) -> None:
        """Record a structured world event and mirror it to the legacy text log."""
        self.world.log_event(description)
        self.world.record_event(
            WorldEventRecord(
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
        )

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
        self._record_world_event(
            result.description,
            kind=result.event_type,
            year=result.year,
            location_id=location_id,
            primary_actor_id=result.affected_characters[0] if result.affected_characters else None,
            secondary_actor_ids=result.affected_characters[1:],
            severity=severity,
        )

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
        for _ in range(years):
            self._run_year()

    def _run_year(self) -> None:
        """Process a single year, distributing events across 12 months."""
        # --- Natural death checks (once per year, month 1) ---
        self.current_month = 1
        for char in list(self.world.characters):
            result = self.event_system.check_natural_death(char, self.world, rng=self.rng)
            if result is not None:
                self._record_event(result, location_id=char.location_id)

        # --- Injury recovery (once per year, month 1) ---
        self._recover_injuries()

        # --- Adventure start / progression (distributed across months) ---
        self.current_month = 2
        self._maybe_start_adventure()
        self._advance_adventures()

        # --- Random events (distributed across 12 months) ---
        for i in range(self.events_per_year):
            self.current_month = (i % 12) + 1
            result = self.event_system.generate_random_event(
                self.world.characters, self.world, rng=self.rng
            )
            if result is None:
                break
            primary_id = result.affected_characters[0] if result.affected_characters else None
            primary_char = self.world.get_character_by_id(primary_id) if primary_id else None
            loc_id = primary_char.location_id if primary_char else None
            self._record_event(result, location_id=loc_id)

        self.current_month = 0
        self.world.advance_time(1)

    def _recover_injuries(self) -> None:
        """Give injured characters a chance to recover during normal life."""
        for char in self.world.characters:
            if not char.alive or char.injury_status != "injured":
                continue
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

    def _maybe_start_adventure(self) -> None:
        """Start at most one new adventure in the current year."""
        candidates = [
            c for c in self.world.characters
            if c.alive and c.active_adventure_id is None and c.injury_status != "injured"
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
            localized_type = tr(f"event_type_{etype}")
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

    def get_latest_yearly_report(self) -> str:
        """Generate and format a yearly report for the most recent completed year."""
        year = self.world.year - 1
        if year < 1000:
            year = self.world.year
        return self.get_yearly_report(year)

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
            "locale": get_locale(),
            "rng_state": repr(self.rng.getstate()),
            "id_rng_state": repr(self.id_rng.getstate()),
            "history": [ev.to_dict() for ev in self.history],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Simulator":
        """Rebuild a simulator from a serialised snapshot."""
        from character import Character
        from world import World

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
        sim.current_month = data.get("current_month", 0)
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
                location_id=run.destination,
                primary_actor_id=run.character_id,
            )
        return True
