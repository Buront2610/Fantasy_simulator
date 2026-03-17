"""
adventure.py - Adventure progression for the Fantasy Simulator.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from i18n import tr


ADVENTURE_DISCOVERIES = [
    "an ancient relic",
    "a pouch of moon-silver",
    "a fragment of lost lore",
    "a cache of monster trophies",
]

CHOICE_PRESS_ON = "press_on"
CHOICE_PROCEED_CAUTIOUSLY = "proceed_cautiously"
CHOICE_RETREAT = "retreat"
CHOICE_WITHDRAW = "withdraw"


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
            summary = tr("summary_adventure_arrived", name=self.character_name, destination=self.destination)
            detail = tr("detail_adventure_arrived", name=self.character_name, origin=self.origin, destination=self.destination)
            self._record(summary, detail)
            if rng.random() < 0.35:
                self.pending_choice = AdventureChoice(
                    prompt=tr("choice_dangerous_approach", name=self.character_name, destination=self.destination),
                    options=[CHOICE_PRESS_ON, CHOICE_PROCEED_CAUTIOUSLY, CHOICE_RETREAT],
                    default_option=CHOICE_PROCEED_CAUTIOUSLY,
                    context="approach",
                )
                self.state = "waiting_for_choice"
                self.detail_log.append(tr("detail_paused_at_entrance", name=self.character_name))
            else:
                self.state = "exploring"
            return [summary]

        if self.state == "exploring":
            self.steps_taken += 1
            roll = rng.random()
            if roll < 0.18:
                self.injury_status = "injured"
                summary = tr("summary_adventure_injured", name=self.character_name)
                detail = tr("detail_adventure_injured", name=self.character_name, destination=self.destination)
                self._record(summary, detail)
                self.state = "returning"
                return [summary]

            if roll < 0.24:
                self.outcome = "death"
                self.state = "resolved"
                self.resolution_year = world.year
                character.alive = False
                character.active_adventure_id = None
                summary = tr("summary_adventure_died", name=self.character_name, destination=self.destination)
                detail = tr("detail_adventure_died", name=self.character_name, destination=self.destination)
                self._record(summary, detail)
                character.add_history(tr("history_adventure_detail", year=world.year, detail=detail))
                return [summary]

            discovery = rng.choice(ADVENTURE_DISCOVERIES)
            self.loot_summary.append(discovery)
            summary = tr("summary_adventure_discovery", name=self.character_name, destination=self.destination)
            detail = tr("detail_adventure_discovery", name=self.character_name, discovery=discovery, destination=self.destination)
            self._record(summary, detail)

            if self.pending_choice is None and rng.random() < 0.40:
                self.pending_choice = AdventureChoice(
                    prompt=tr("choice_press_deeper", name=self.character_name, destination=self.destination),
                    options=[CHOICE_PRESS_ON, CHOICE_WITHDRAW],
                    default_option=CHOICE_WITHDRAW,
                    context="depth",
                )
                self.state = "waiting_for_choice"
                self.detail_log.append(tr("detail_paused_to_delve", name=self.character_name))
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
                    summary = tr("summary_returned_injured", name=self.character_name, destination=self.destination)
                    detail = tr("detail_returned_injured", name=self.character_name, origin=self.origin)
                elif self.loot_summary:
                    self.outcome = "safe_return"
                    summary = tr("summary_returned_safely", name=self.character_name, destination=self.destination, loot=self.loot_summary[-1])
                    detail = tr("detail_returned_safely", name=self.character_name, origin=self.origin, items=", ".join(self.loot_summary))
                else:
                    self.outcome = "retreat"
                    summary = tr("summary_retreated_safely", name=self.character_name, destination=self.destination)
                    detail = tr("detail_retreated_safely", name=self.character_name, origin=self.origin)
                self._record(summary, detail)
            character.active_adventure_id = None
            character.add_history(tr("history_adventure_detail", year=world.year, detail=self.detail_log[-1]))
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

        detail = tr("detail_choice_made", name=self.character_name, choice=tr(f"choice_{chosen}"))
        self.detail_log.append(detail)

        context = self.pending_choice.context
        self.pending_choice = None

        if chosen in (CHOICE_RETREAT, CHOICE_WITHDRAW):
            self.state = "returning"
            summary = tr("summary_choice_withdraw", name=self.character_name)
            self.summary_log.append(summary)
            self.detail_log.append(tr("detail_choice_withdraw", name=self.character_name))
            return [summary]

        if context == "approach" and chosen == CHOICE_PROCEED_CAUTIOUSLY:
            self.state = "exploring"
            self.detail_log.append(tr("detail_choice_cautious", name=self.character_name, destination=self.destination))
            return []

        if context in ("approach", "depth") and chosen == CHOICE_PRESS_ON:
            self.state = "exploring"
            self.detail_log.append(tr("detail_choice_press_on", name=self.character_name, destination=self.destination))
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
    destination = rng.choice(risky) if risky else world.random_location(rng=rng)

    run = AdventureRun(
        character_id=character.char_id,
        character_name=character.name,
        origin=character.location,
        destination=destination.name,
        year_started=world.year,
    )
    run._record(
        tr("summary_adventure_set_out", name=character.name, origin=character.location, destination=destination.name),
        tr("detail_adventure_set_out", name=character.name, origin=character.location, destination=destination.name),
    )
    return run
