"""
simulator.py - Orchestrates the world simulation loop.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from events import EventResult, EventSystem


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
        world: Any,
        events_per_year: int = 8,
        seed: Optional[int] = None,
    ) -> None:
        self.world = world
        self.events_per_year = events_per_year
        self.event_system = EventSystem()
        self.history: List[EventResult] = []  # all events across all years
        if seed is not None:
            random.seed(seed)

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
        for _ in range(years):
            self._run_year()

    def _run_year(self) -> None:
        """Process a single year."""
        # --- Natural death checks ---
        for char in list(self.world.characters):
            result = self.event_system.check_natural_death(char, self.world)
            if result is not None:
                self.history.append(result)
                self.world.log_event(result.description)

        # --- Random events ---
        alive = [c for c in self.world.characters if c.alive]
        if not alive:
            self.world.advance_time(1)
            return

        for _ in range(self.events_per_year):
            result = self.event_system.generate_random_event(
                self.world.characters, self.world
            )
            if result is not None:
                self.history.append(result)
                self.world.log_event(result.description)

        self.world.advance_time(1)

    # ------------------------------------------------------------------
    # Summary & stories
    # ------------------------------------------------------------------

    def get_summary(self) -> str:
        """Return a human-readable summary of the entire simulation."""
        total = len(self.history)
        alive = sum(1 for c in self.world.characters if c.alive)
        dead  = sum(1 for c in self.world.characters if not c.alive)

        type_counts: Dict[str, int] = {}
        for ev in self.history:
            type_counts[ev.event_type] = type_counts.get(ev.event_type, 0) + 1

        lines = [
            "=" * 60,
            f"  SIMULATION SUMMARY — {self.world.name}",
            f"  Final year: {self.world.year}",
            "=" * 60,
            f"  Total events recorded : {total}",
            f"  Characters alive      : {alive}",
            f"  Characters deceased   : {dead}",
            "",
            "  Event breakdown:",
        ]
        for etype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"    {etype:<20} {count:>4} times")

        lines.append("")
        lines.append("  Notable moments:")
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
            return f"No character with ID '{char_id}' found."

        lines = [
            "─" * 50,
            f"  The Story of {char.name}",
            f"  {char.race} {char.job}",
            "─" * 50,
        ]
        if char.history:
            for entry in char.history:
                lines.append(f"  • {entry}")
        else:
            lines.append("  (No notable events recorded.)")

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
