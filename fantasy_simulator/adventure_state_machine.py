"""State progression for active adventure runs."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, List, Type

from .adventure_choices import AdventureChoiceResolver
from .adventure_constants import (
    ADVENTURE_DISCOVERIES,
    BASE_CRITICAL_RATIO,
    CHOICE_PRESS_ON,
    CHOICE_PROCEED_CAUTIOUSLY,
    CHOICE_RETREAT,
    CHOICE_WITHDRAW,
)
from .adventure_policy import AdventurePolicyEngine
from .adventure_protocols import AdventureRunLike
from .i18n import tr, tr_term

if TYPE_CHECKING:
    from .character import Character
    from .world import World


class AdventureStateMachine:
    def __init__(self, run: AdventureRunLike, choice_cls: Type[Any]) -> None:
        self.run = run
        self.choice_cls = choice_cls
        self.policy = AdventurePolicyEngine(run)

    def step(self, character: "Character", world: "World", rng: Any = random) -> List[str]:
        if self.run.is_resolved:
            return []

        if self.run.state == "waiting_for_choice":
            return AdventureChoiceResolver(self.run).resolve(world, character, option=None)

        destination_name = world.location_name(self.run.destination)
        origin_name = world.location_name(self.run.origin)

        if self.run.state == "traveling":
            return self._step_traveling(world, rng, destination_name, origin_name)
        if self.run.state == "exploring":
            return self._step_exploring(character, world, rng, destination_name, origin_name)
        if self.run.state == "returning":
            return self._step_returning(character, world, destination_name, origin_name)
        return []

    def _step_traveling(
        self,
        world: "World",
        rng: Any,
        destination_name: str,
        origin_name: str,
    ) -> List[str]:
        self.run.steps_taken += 1
        summary = tr("summary_adventure_arrived", name=self.run.character_name, destination=destination_name)
        detail = tr(
            "detail_adventure_arrived",
            name=self.run.character_name,
            origin=origin_name,
            destination=destination_name,
        )
        self.run._record(summary, detail)
        if rng.random() < 0.35:
            self.run.pending_choice = self.choice_cls(
                prompt=tr(
                    "choice_dangerous_approach",
                    name=self.run.character_name,
                    destination=destination_name,
                ),
                options=[CHOICE_PRESS_ON, CHOICE_PROCEED_CAUTIOUSLY, CHOICE_RETREAT],
                default_option=self.policy.default_option_for_context("approach"),
                context="approach",
            )
            self.run.state = "waiting_for_choice"
            self.run.detail_log.append(tr("detail_paused_at_entrance", name=self.run.character_name))
        else:
            self.run.state = "exploring"
        return [summary]

    def _step_exploring(
        self,
        character: "Character",
        world: "World",
        rng: Any,
        destination_name: str,
        origin_name: str,
    ) -> List[str]:
        self.run.steps_taken += 1
        members = self.policy.party_members(world) or [character]

        if self.run.is_party and self.policy.should_auto_retreat(members):
            self.run.state = "returning"
            summary = tr("summary_party_retreated_auto", name=self.run.character_name, destination=destination_name)
            detail = tr("detail_party_retreated_auto", name=self.run.character_name, destination=destination_name)
            self.run._record(summary, detail)
            return [summary]

        if self.run.is_party:
            self.policy.tick_supply(rng)

        injury_chance = self.policy.compute_injury_chance(members)
        critical_chance = min(injury_chance * BASE_CRITICAL_RATIO, 0.60)
        roll = rng.random()
        injured_member = character
        if self.run.is_party and members:
            injured_member = rng.choice(members)

        if roll < injury_chance:
            return self._resolve_hazard_band(injured_member, character, world, destination_name)
        if roll < critical_chance:
            return self._resolve_nonfatal_injury(injured_member, destination_name)

        loot_chance = self.policy.compute_loot_chance(members)
        if rng.random() < loot_chance:
            discovery = rng.choice(ADVENTURE_DISCOVERIES)
            self.run.loot_summary.append(discovery)
            summary = tr("summary_adventure_discovery", name=self.run.character_name, destination=destination_name)
            detail = tr(
                "detail_adventure_discovery",
                name=self.run.character_name,
                discovery=tr_term(discovery),
                destination=destination_name,
            )
            self.run._record(summary, detail)
        else:
            summary = tr("summary_adventure_scouting", name=self.run.character_name, destination=destination_name)
            detail = tr("detail_adventure_scouting", name=self.run.character_name, destination=destination_name)
            self.run._record(summary, detail)

        if self.run.pending_choice is None and rng.random() < 0.40:
            self.run.pending_choice = self.choice_cls(
                prompt=tr("choice_press_deeper", name=self.run.character_name, destination=destination_name),
                options=[CHOICE_PRESS_ON, CHOICE_WITHDRAW],
                default_option=self.policy.default_option_for_context("depth"),
                context="depth",
            )
            self.run.state = "waiting_for_choice"
            self.run.detail_log.append(tr("detail_paused_to_delve", name=self.run.character_name))
        else:
            self.run.state = "returning"
        return [self.run.summary_log[-1]]

    def _resolve_hazard_band(
        self,
        injured_member: "Character",
        leader: "Character",
        world: "World",
        destination_name: str,
    ) -> List[str]:
        if injured_member.injury_status == "dying":
            self.run.outcome = "death"
            self.run.state = "resolved"
            self.run.resolution_year = world.year
            injured_member.alive = False
            injured_member.active_adventure_id = None
            self.run.death_member_id = injured_member.char_id
            leader.active_adventure_id = None
            self.run._clear_member_adventures(world)
            summary = tr("summary_adventure_died", name=injured_member.name, destination=destination_name)
            detail = tr("detail_adventure_died", name=injured_member.name, destination=destination_name)
            self.run._record(summary, detail)
            injured_member.add_history(tr("history_adventure_detail", year=world.year, detail=detail))
            return [summary]
        return self._resolve_nonfatal_injury(injured_member, destination_name)

    def _resolve_nonfatal_injury(
        self,
        injured_member: "Character",
        destination_name: str,
    ) -> List[str]:
        injured_member.worsen_injury()
        self.run.injury_status = injured_member.injury_status
        self.run.injury_member_id = injured_member.char_id
        summary = tr("summary_adventure_injured", name=injured_member.name)
        detail = tr("detail_adventure_injured", name=injured_member.name, destination=destination_name)
        self.run._record(summary, detail)
        self.run.state = "returning"
        return [summary]

    def _step_returning(
        self,
        character: "Character",
        world: "World",
        destination_name: str,
        origin_name: str,
    ) -> List[str]:
        self.run.steps_taken += 1
        self.run.state = "resolved"
        self.run.resolution_year = world.year
        history_target = character
        if self.run.outcome != "death":
            if self.run.injury_status != "none":
                self.run.outcome = "injury"
                injured_member = world.get_character_by_id(self.run.injury_member_id or self.run.character_id)
                if injured_member is None:
                    injured_member = character
                injured_member.injury_status = self.run.injury_status
                summary = tr("summary_returned_injured", name=injured_member.name, destination=destination_name)
                detail = tr("detail_returned_injured", name=injured_member.name, origin=origin_name)
                history_target = injured_member
            elif self.run.loot_summary:
                self.run.outcome = "safe_return"
                summary = tr(
                    "summary_returned_safely",
                    name=self.run.character_name,
                    destination=destination_name,
                    loot=tr_term(self.run.loot_summary[-1]),
                )
                detail = tr(
                    "detail_returned_safely",
                    name=self.run.character_name,
                    origin=origin_name,
                    items=", ".join(tr_term(item) for item in self.run.loot_summary),
                )
            else:
                self.run.outcome = "retreat"
                summary = tr("summary_retreated_safely", name=self.run.character_name, destination=destination_name)
                detail = tr("detail_retreated_safely", name=self.run.character_name, origin=origin_name)
            self.run._record(summary, detail)
        character.active_adventure_id = None
        self.run._clear_member_adventures(world)
        history_target.add_history(tr("history_adventure_detail", year=world.year, detail=self.run.detail_log[-1]))
        return [self.run.summary_log[-1]]
