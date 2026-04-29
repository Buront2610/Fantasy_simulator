"""Pending choice resolution for adventures."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from .adventure_constants import (
    CHOICE_PRESS_ON,
    CHOICE_PROCEED_CAUTIOUSLY,
    CHOICE_RETREAT,
    CHOICE_WITHDRAW,
)
from .adventure_protocols import AdventureRunLike
from .i18n import tr

if TYPE_CHECKING:
    from .character import Character
    from .world import World


class AdventureChoiceResolver:
    def __init__(self, run: AdventureRunLike) -> None:
        self.run = run

    def resolve(
        self,
        world: "World",
        character: "Character",
        option: Optional[str] = None,
    ) -> List[str]:
        if self.run.pending_choice is None:
            return []

        chosen = option or self.run.pending_choice.default_option
        if chosen not in self.run.pending_choice.options:
            chosen = self.run.pending_choice.default_option
        self.run.pending_choice.selected_option = chosen

        detail = tr("detail_choice_made", name=self.run.character_name, choice=tr(f"choice_{chosen}"))
        self.run.detail_log.append(detail)

        context = self.run.pending_choice.context
        self.run.pending_choice = None

        if chosen in (CHOICE_RETREAT, CHOICE_WITHDRAW):
            self.run.state = "returning"
            summary = tr("summary_choice_withdraw", name=self.run.character_name)
            self.run.summary_log.append(summary)
            self.run.detail_log.append(tr("detail_choice_withdraw", name=self.run.character_name))
            return [summary]

        if context == "approach" and chosen == CHOICE_PROCEED_CAUTIOUSLY:
            self.run.state = "exploring"
            destination_name = world.location_name(self.run.destination)
            self.run.detail_log.append(
                tr("detail_choice_cautious", name=self.run.character_name, destination=destination_name)
            )
            return []

        if context in ("approach", "depth") and chosen == CHOICE_PRESS_ON:
            self.run.state = "exploring"
            destination_name = world.location_name(self.run.destination)
            self.run.detail_log.append(
                tr("detail_choice_press_on", name=self.run.character_name, destination=destination_name)
            )
            return []

        self.run.state = "exploring"
        return []
