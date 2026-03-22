"""
simulator.py - Orchestrates the world simulation loop.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import random

from adventure import AdventureRun, create_adventure_run
from events import EventResult, EventSystem, WorldEventRecord
from i18n import get_locale, set_locale, tr, tr_term

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
        self.history: List[EventResult] = []  # all events across all years
        self.rng = random.Random(seed)

    # Severity scale: 1=minor, 2=notable, 3=significant, 4=major, 5=critical
    _SEVERITY_MAP: Dict[str, int] = {
        "death": 5, "battle_fatal": 5, "marriage": 4,
        "discovery": 3, "battle": 3, "journey": 2,
        "meeting": 1, "aging": 1, "skill_training": 1,
        "romance": 2, "anniversary": 2,
    }

    def _record_event(self, result: EventResult, location_id: Optional[str] = None) -> None:
        """Log an event as both a string and a structured WorldEventRecord."""
        self.history.append(result)
        self.world.log_event(result.description)
        severity = self._SEVERITY_MAP.get(result.event_type, 1)
        record = WorldEventRecord.from_event_result(result, location_id=location_id, severity=severity)
        self.world.record_event(record)

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
        """Process a single year."""
        # --- Natural death checks ---
        for char in list(self.world.characters):
            result = self.event_system.check_natural_death(char, self.world, rng=self.rng)
            if result is not None:
                self._record_event(result, location_id=char.location_id)

        # --- Injury recovery ---
        self._recover_injuries()

        # --- Adventure start / progression ---
        self._maybe_start_adventure()
        self._advance_adventures()

        # --- Random events ---
        for _ in range(self.events_per_year):
            result = self.event_system.generate_random_event(
                self.world.characters, self.world, rng=self.rng
            )
            if result is None:
                break
            primary_id = result.affected_characters[0] if result.affected_characters else None
            primary_char = self.world.get_character_by_id(primary_id) if primary_id else None
            loc_id = primary_char.location_id if primary_char else None
            self._record_event(result, location_id=loc_id)

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
                self.world.log_event(message)

    def _maybe_start_adventure(self) -> None:
        """Start at most one new adventure in the current year."""
        candidates = [
            c for c in self.world.characters
            if c.alive and c.active_adventure_id is None and c.injury_status != "injured"
        ]
        if not candidates or self.rng.random() >= 0.25:
            return

        char = self.rng.choice(candidates)
        run = create_adventure_run(char, self.world, rng=self.rng)
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
        self.world.log_event(run.summary_log[-1])

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
                summaries = run.step(char, self.world, rng=self.rng)
                for entry in summaries:
                    self.world.log_event(entry)
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
        """Return a human-readable summary of the entire simulation."""
        total = len(self.history)
        alive = sum(1 for c in self.world.characters if c.alive)
        dead = sum(1 for c in self.world.characters if not c.alive)

        type_counts: Dict[str, int] = {}
        for ev in self.history:
            type_counts[ev.event_type] = type_counts.get(ev.event_type, 0) + 1

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
        # Pick up to 5 dramatic events
        dramatic = [
            ev for ev in self.history
            if ev.event_type in ("marriage", "battle_fatal", "death", "discovery")
        ]
        shown = dramatic[:5] if len(dramatic) >= 5 else dramatic
        for ev in shown:
            lines.append(f"    • {ev.description}")

        lines.append("=" * 60)
        return "\n".join(lines)

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
        """Return world event log entries, optionally only the last *n*."""
        log = self.world.event_log
        if last_n is not None:
            return log[-last_n:]
        return log

    def events_by_type(self, event_type: str) -> List[EventResult]:
        """Return all EventResults of the given type."""
        return [ev for ev in self.history if ev.event_type == event_type]

    def to_dict(self) -> Dict[str, Any]:
        """Serialise simulator state, including world and history."""
        return {
            "world": self.world.to_dict(),
            "characters": [char.to_dict() for char in self.world.characters],
            "events_per_year": self.events_per_year,
            "adventure_steps_per_year": self.adventure_steps_per_year,
            "locale": get_locale(),
            "rng_state": repr(self.rng.getstate()),
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
        world._char_index = {c.char_id: c for c in characters}
        sim = cls(
            world,
            events_per_year=data.get("events_per_year", 8),
            adventure_steps_per_year=data.get("adventure_steps_per_year", 3),
        )
        set_locale(data.get("locale", get_locale()))
        rng_state = data.get("rng_state")
        if rng_state is not None:
            try:
                parsed = ast.literal_eval(rng_state)
                # Validate Mersenne Twister state structure: (version, internalstate, gauss_next)
                if (
                    isinstance(parsed, tuple)
                    and len(parsed) == 3
                    and isinstance(parsed[0], int)
                    and isinstance(parsed[1], tuple)
                ):
                    sim.rng.setstate(parsed)
            except (ValueError, SyntaxError, TypeError):
                pass  # Ignore corrupted RNG state; start with fresh RNG
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
            self.world.log_event(entry)
        return True
