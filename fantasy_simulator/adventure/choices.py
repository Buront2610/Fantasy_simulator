"""Pending choice resolution for adventures."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .constants import (
    CHOICE_PRESS_ON,
    CHOICE_PROCEED_CAUTIOUSLY,
    CHOICE_RETREAT,
    CHOICE_WITHDRAW,
)
from .protocols import AdventureRunLike
from .results import AdventureStepResult, step_fact_result
from ..i18n import tr

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World


class AdventureChoiceResolver:
    def __init__(self, run: AdventureRunLike) -> None:
        self.run = run

    def resolve(
        self,
        world: "World",
        character: "Character",
        option: Optional[str] = None,
    ) -> AdventureStepResult:
        if self.run.pending_choice is None:
            return AdventureStepResult(self.run.adventure_id, self.run.state)

        chosen = option or self.run.pending_choice.default_option
        if chosen not in self.run.pending_choice.options:
            chosen = self.run.pending_choice.default_option
        self.run.pending_choice.selected_option = chosen
        if self.run.schedule is not None:
            self.run.schedule.segment_mode = {
                CHOICE_PROCEED_CAUTIOUSLY: "cautious", CHOICE_PRESS_ON: "swift",
            }.get(chosen, "standard")

        detail = tr("detail_choice_made", name=self.run.character_name, choice=tr(f"choice_{chosen}"))
        self.run.detail_log.append(detail)

        context = self.run.pending_choice.context
        self.run.pending_choice = None

        if chosen in (CHOICE_RETREAT, CHOICE_WITHDRAW):
            self.run.state = "returning"
            summary = tr("summary_choice_withdraw", name=self.run.character_name)
            self.run.summary_log.append(summary)
            self.run.detail_log.append(tr("detail_choice_withdraw", name=self.run.character_name))
            return self._result(chosen, context, "summary_choice_withdraw", show_summary=True)

        if context == "approach" and chosen == CHOICE_PROCEED_CAUTIOUSLY:
            self.run.state = "exploring"
            destination_name = world.location_name(self.run.destination)
            self.run.detail_log.append(
                tr("detail_choice_cautious", name=self.run.character_name, destination=destination_name)
            )
            return self._result(chosen, context)

        if context in ("approach", "depth") and chosen == CHOICE_PRESS_ON:
            self.run.state = "exploring"
            destination_name = world.location_name(self.run.destination)
            self.run.detail_log.append(
                tr("detail_choice_press_on", name=self.run.character_name, destination=destination_name)
            )
            return self._result(chosen, context)

        self.run.state = "exploring"
        return self._result(chosen, context)

    def _result(
        self, chosen: str, context: str, summary_key: str = "detail_choice_made", *, show_summary: bool = False,
    ) -> AdventureStepResult:
        return step_fact_result(
            self.run, "adventure_choice", summary_key,
            {"name": self.run.character_name, "choice": tr(f"choice_{chosen}"),
             "choice_key": f"choice_{chosen}", "selected_option": chosen, "choice_context": context},
            show_summary=show_summary,
        )
