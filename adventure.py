"""
adventure.py - Adventure progression for the Fantasy Simulator.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


ADVENTURE_DISCOVERIES = [
    "an ancient relic",
    "a pouch of moon-silver",
    "a fragment of lost lore",
    "a cache of monster trophies",
]


@dataclass
class AdventureChoice:
    """A single pending player-facing choice for an adventure."""

    prompt: str
    options: List[str]
    default_option: str
    context: str
    selected_option: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt": self.prompt,
            "options": list(self.options),
            "default_option": self.default_option,
            "context": self.context,
            "selected_option": self.selected_option,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdventureChoice":
        return cls(
            prompt=data["prompt"],
            options=list(data["options"]),
            default_option=data["default_option"],
            context=data["context"],
            selected_option=data.get("selected_option"),
        )


@dataclass
class AdventureRun:
    """Represents one ongoing adventure inside the main world simulation."""

    character_id: str
    character_name: str
    origin: str
    destination: str
    year_started: int
    adventure_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    state: str = "traveling"
    injury_status: str = "none"
    steps_taken: int = 0
    pending_choice: Optional[AdventureChoice] = None
    outcome: Optional[str] = None
    loot_summary: List[str] = field(default_factory=list)
    summary_log: List[str] = field(default_factory=list)
    detail_log: List[str] = field(default_factory=list)
    resolution_year: Optional[int] = None

    @property
    def is_resolved(self) -> bool:
        return self.state == "resolved"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "character_id": self.character_id,
            "character_name": self.character_name,
            "origin": self.origin,
            "destination": self.destination,
            "year_started": self.year_started,
            "adventure_id": self.adventure_id,
            "state": self.state,
            "injury_status": self.injury_status,
            "steps_taken": self.steps_taken,
            "pending_choice": (
                self.pending_choice.to_dict() if self.pending_choice is not None else None
            ),
            "outcome": self.outcome,
            "loot_summary": list(self.loot_summary),
            "summary_log": list(self.summary_log),
            "detail_log": list(self.detail_log),
            "resolution_year": self.resolution_year,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdventureRun":
        pending = data.get("pending_choice")
        return cls(
            character_id=data["character_id"],
            character_name=data["character_name"],
            origin=data["origin"],
            destination=data["destination"],
            year_started=data["year_started"],
            adventure_id=data.get("adventure_id", uuid.uuid4().hex[:10]),
            state=data.get("state", "traveling"),
            injury_status=data.get("injury_status", "none"),
            steps_taken=data.get("steps_taken", 0),
            pending_choice=AdventureChoice.from_dict(pending) if pending else None,
            outcome=data.get("outcome"),
            loot_summary=list(data.get("loot_summary", [])),
            summary_log=list(data.get("summary_log", [])),
            detail_log=list(data.get("detail_log", [])),
            resolution_year=data.get("resolution_year"),
        )

    def step(self, character: Any, world: Any, rng: Any = random) -> List[str]:
        """Advance the adventure by one internal step."""
        if self.is_resolved:
            return []

        if self.state == "waiting_for_choice":
            return self.resolve_choice(world, character, option=None)

        if self.state == "traveling":
            self.steps_taken += 1
            summary = (
                f"{self.character_name} reached {self.destination} and began the expedition."
            )
            detail = (
                f"{self.character_name} left {self.origin}, arrived at {self.destination}, "
                "and started scouting the area."
            )
            self._record(summary, detail)
            if rng.random() < 0.35:
                self.pending_choice = AdventureChoice(
                    prompt=f"{self.character_name} found a dangerous approach into {self.destination}.",
                    options=["press_on", "proceed_cautiously", "retreat"],
                    default_option="proceed_cautiously",
                    context="approach",
                )
                self.state = "waiting_for_choice"
                self.detail_log.append(
                    f"{self.character_name} paused for a decision at the entrance."
                )
            else:
                self.state = "exploring"
            return [summary]

        if self.state == "exploring":
            self.steps_taken += 1
            roll = rng.random()
            if roll < 0.18:
                self.injury_status = "injured"
                summary = f"{self.character_name} was injured during the expedition and pulled back."
                detail = (
                    f"{self.character_name} suffered an injury while exploring {self.destination} "
                    "and decided to withdraw."
                )
                self._record(summary, detail)
                self.state = "returning"
                return [summary]

            if roll < 0.24:
                self.outcome = "death"
                self.state = "resolved"
                self.resolution_year = world.year
                character.alive = False
                character.active_adventure_id = None
                summary = f"{self.character_name} died on an adventure near {self.destination}."
                detail = (
                    f"{self.character_name} was lost during the expedition at {self.destination} "
                    "and never returned."
                )
                self._record(summary, detail)
                character.add_history(f"Year {world.year}: {detail}")
                return [summary]

            discovery = rng.choice(ADVENTURE_DISCOVERIES)
            self.loot_summary.append(discovery)
            summary = f"{self.character_name} made a discovery at {self.destination}."
            detail = f"{self.character_name} discovered {discovery} at {self.destination}."
            self._record(summary, detail)

            if self.pending_choice is None and rng.random() < 0.40:
                self.pending_choice = AdventureChoice(
                    prompt=f"{self.character_name} can press deeper into {self.destination}.",
                    options=["press_on", "withdraw"],
                    default_option="withdraw",
                    context="depth",
                )
                self.state = "waiting_for_choice"
                self.detail_log.append(
                    f"{self.character_name} paused to decide whether to delve deeper."
                )
            else:
                self.state = "returning"
            return [summary]

        if self.state == "returning":
            self.steps_taken += 1
            self.state = "resolved"
            self.resolution_year = world.year
            if self.outcome != "death":
                if self.injury_status != "none":
                    self.outcome = "injury"
                    character.injury_status = self.injury_status
                    summary = (
                        f"{self.character_name} returned from {self.destination} injured."
                    )
                    detail = (
                        f"{self.character_name} made it back to {self.origin}, but carried injuries "
                        "from the expedition."
                    )
                elif self.loot_summary:
                    self.outcome = "safe_return"
                    summary = (
                        f"{self.character_name} returned safely from {self.destination} "
                        f"with {self.loot_summary[-1]}."
                    )
                    detail = (
                        f"{self.character_name} returned safely to {self.origin} after recovering "
                        f"{', '.join(self.loot_summary)}."
                    )
                else:
                    self.outcome = "retreat"
                    summary = (
                        f"{self.character_name} retreated from {self.destination} and returned safely."
                    )
                    detail = (
                        f"{self.character_name} abandoned the expedition and returned to {self.origin} "
                        "without major findings."
                    )
                self._record(summary, detail)
            character.active_adventure_id = None
            character.add_history(f"Year {world.year}: {self.detail_log[-1]}")
            return [self.summary_log[-1]]

        return []

    def resolve_choice(
        self,
        world: Any,
        character: Any,
        option: Optional[str] = None,
    ) -> List[str]:
        """Resolve the current pending choice or apply its default option."""
        if self.pending_choice is None:
            return []

        chosen = option or self.pending_choice.default_option
        if chosen not in self.pending_choice.options:
            chosen = self.pending_choice.default_option
        self.pending_choice.selected_option = chosen

        detail = f"{self.character_name} chose '{chosen}' during the expedition."
        self.detail_log.append(detail)

        context = self.pending_choice.context
        self.pending_choice = None

        if chosen in ("retreat", "withdraw"):
            self.state = "returning"
            summary = f"{self.character_name} chose to withdraw from the expedition."
            self.summary_log.append(summary)
            self.detail_log.append(
                f"{self.character_name} stopped pushing deeper and began the return journey."
            )
            return [summary]

        if context == "approach" and chosen == "proceed_cautiously":
            self.state = "exploring"
            self.detail_log.append(
                f"{self.character_name} took a cautious route into {self.destination}."
            )
            return []

        if context in ("approach", "depth") and chosen == "press_on":
            self.state = "exploring"
            self.detail_log.append(
                f"{self.character_name} pressed deeper into {self.destination}."
            )
            return []

        self.state = "exploring"
        return []

    def _record(self, summary: str, detail: str) -> None:
        self.summary_log.append(summary)
        self.detail_log.append(detail)


def create_adventure_run(character: Any, world: Any, rng: Any = random) -> AdventureRun:
    """Create a new adventure for a character using nearby risky terrain when possible."""
    neighbors = world.get_neighboring_locations(character.location)
    risky = [loc for loc in neighbors if loc.region_type in ("forest", "mountain", "dungeon")]
    if not risky:
        risky = [
            loc for loc in world.grid.values()
            if loc.region_type in ("forest", "mountain", "dungeon")
        ]
    destination = rng.choice(risky) if risky else world.random_location()

    run = AdventureRun(
        character_id=character.char_id,
        character_name=character.name,
        origin=character.location,
        destination=destination.name,
        year_started=world.year,
    )
    run._record(
        f"{character.name} set out from {character.location} toward {destination.name}.",
        f"{character.name} began an expedition from {character.location} toward {destination.name}.",
    )
    return run
