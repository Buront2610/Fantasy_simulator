"""State progression for active adventure runs."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Type

from .choices import AdventureChoiceResolver
from .constants import (
    BASE_CRITICAL_RATIO,
    CHOICE_PRESS_ON,
    CHOICE_PROCEED_CAUTIOUSLY,
    CHOICE_RETREAT,
    CHOICE_WITHDRAW,
)
from .hazards import (
    resolve_critical_hazard,
    resolve_hazard_band,
)
from .policy import AdventurePolicyEngine
from .rescue import perform_rescue
from .protocols import AdventureRunLike
from .roles import capability
from .rewards import find_discovery
from .cargo import complete_cargo_return, deliver_cargo
from .results import AdventureFactKind, AdventureStepResult, step_fact_result
from ..character_model.death_resolution import mark_character_dead
from ..i18n import tr, tr_term

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World


class AdventureStateMachine:
    def __init__(self, run: AdventureRunLike, choice_cls: Type[Any]) -> None:
        self.run = run
        self.choice_cls = choice_cls
        self.policy = AdventurePolicyEngine(run)

    def step(self, character: "Character", world: "World", rng: Any = random) -> AdventureStepResult:
        if self.run.is_resolved:
            return AdventureStepResult(self.run.adventure_id, self.run.state)

        if self.run.state == "waiting_for_choice":
            return AdventureChoiceResolver(self.run).resolve(world, character, option=None)

        destination_name = world.location_name(self.run.destination)
        origin_name = world.location_name(self.run.origin)

        if self.run.state == "traveling":
            return self._step_traveling(world, rng, destination_name, origin_name)
        if self.run.state == "exploring":
            result = self._step_exploring(character, world, rng, destination_name, origin_name)
            if self.run.schedule is not None:
                self.run.schedule.segment_mode = (
                    self.run.objective.pace if self.run.objective is not None else "standard"
                )
            return result
        if self.run.state == "returning":
            return self._step_returning(character, world, destination_name, origin_name)
        return AdventureStepResult(self.run.adventure_id, self.run.state)

    def _step_traveling(
        self,
        world: "World",
        rng: Any,
        destination_name: str,
        origin_name: str,
    ) -> AdventureStepResult:
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
        return step_fact_result(self.run, "adventure_arrived", "summary_adventure_arrived",
                                {"name": self.run.character_name, "destination": destination_name}, severity=2)

    def _step_exploring(
        self,
        character: "Character",
        world: "World",
        rng: Any,
        destination_name: str,
        origin_name: str,
    ) -> AdventureStepResult:
        self.run.steps_taken += 1
        members = self.policy.party_members(world) or [character]

        if (self.run.is_party or self.run.objective is not None) and self.policy.should_auto_retreat(members):
            self.run.state = "returning"
            summary = tr("summary_party_retreated_auto", name=self.run.character_name, destination=destination_name)
            detail = tr("detail_party_retreated_auto", name=self.run.character_name, destination=destination_name)
            self.run._record(summary, detail)
            return step_fact_result(self.run, "adventure_retreat_started", "summary_party_retreated_auto",
                                    {"name": self.run.character_name, "destination": destination_name})

        if self.run.is_party and self.run.schedule is None:
            self.policy.tick_supply(rng)

        injury_chance = self.policy.compute_injury_chance(members)
        critical_chance = min(injury_chance * BASE_CRITICAL_RATIO, 0.60)
        roll = rng.random()
        injured_member = character
        if self.run.objective is not None:
            holder = capability(members, "frontline").holder_id
            injured_member = next((member for member in members if member.char_id == holder), character)
        elif self.run.is_party and members:
            injured_member = rng.choice(members)

        if roll < injury_chance:
            return resolve_hazard_band(self.run, injured_member, character, world, rng, destination_name)
        if roll < critical_chance:
            return resolve_critical_hazard(self.run, injured_member, world, rng, destination_name)

        rescue_result = deliver_cargo(world, self.run) or perform_rescue(world, self.run)
        if rescue_result is not None:
            return rescue_result

        kind: AdventureFactKind
        discovery, asset_details = None, {}
        loot_chance = self.policy.compute_loot_chance(members)
        reward = find_discovery(world, self.run, members, rng) if rng.random() < loot_chance else None
        if reward is not None:
            discovery, asset_details = reward.label, reward.details
            self.run.loot_summary.append(discovery)
            kind, summary_key = "adventure_discovery", "summary_adventure_discovery"
            summary = tr("summary_adventure_discovery", name=self.run.character_name, destination=destination_name)
            detail = tr(
                "detail_adventure_discovery",
                name=self.run.character_name,
                discovery=tr_term(discovery),
                destination=destination_name,
            )
            self.run._record(summary, detail)
        else:
            kind, summary_key = "adventure_scouted", "summary_adventure_scouting"
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
        return step_fact_result(
            self.run, kind, summary_key,
            {"name": self.run.character_name, "destination": destination_name,
             "discovery": discovery, **asset_details}, severity=2,
        )

    def _step_returning(
        self,
        character: "Character",
        world: "World",
        destination_name: str,
        origin_name: str,
    ) -> AdventureStepResult:
        cargo_return = complete_cargo_return(world, self.run, character)
        if cargo_return is not None:
            return cargo_return
        self.run.steps_taken += 1
        self.run.state = "resolved"
        self.run.resolution_year = world.year
        history_target = character
        kind: AdventureFactKind
        kind, summary_key, severity = "adventure_death", "summary_adventure_died", 5
        # Character owns current health; the run may still describe an injury since treated or worsened.
        members = [world.get_character_by_id(member_id) for member_id in self.run.member_ids]
        current_members = [member for member in members if member is not None] or [character]
        health_order = {"none": 0, "injured": 1, "serious": 2, "dying": 3}
        injured_member = min(
            current_members,
            key=lambda member: (member.alive, -health_order[member.injury_status], member.char_id),
        )
        self.run.injury_status = injured_member.injury_status
        self.run.injury_member_id = injured_member.char_id if injured_member.injury_status != "none" else None
        if self.run.outcome != "death":
            if not injured_member.alive:
                mark_character_dead(injured_member, world)
                self.run.outcome = "death"
                kind, summary_key, severity = "adventure_death", "summary_adventure_died", 5
                self.run.death_member_id = injured_member.char_id
                summary = tr("summary_adventure_died", name=injured_member.name, destination=destination_name)
                detail = tr("detail_adventure_died", name=injured_member.name, destination=destination_name)
                history_target = injured_member
            elif self.run.injury_status != "none":
                self.run.outcome = "injury"
                kind, summary_key, severity = "adventure_returned_injured", "summary_returned_injured", 3
                summary = tr("summary_returned_injured", name=injured_member.name, destination=destination_name)
                detail = tr("detail_returned_injured", name=injured_member.name, origin=origin_name)
                history_target = injured_member
            elif self.run.loot_summary:
                self.run.outcome = "safe_return"
                kind, summary_key, severity = "adventure_returned", "summary_returned_safely", 2
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
                kind, summary_key, severity = "adventure_retreated", "summary_retreated_safely", 1
                summary = tr("summary_retreated_safely", name=self.run.character_name, destination=destination_name)
                detail = tr("detail_retreated_safely", name=self.run.character_name, origin=origin_name)
            self.run._record(summary, detail)
        character.active_adventure_id = None
        self.run._clear_member_adventures(world)
        history_target.add_history(tr("history_adventure_detail", year=world.year, detail=self.run.detail_log[-1]))
        return step_fact_result(
            self.run, kind, summary_key,
            {"name": history_target.name, "destination": destination_name,
             "loot": tr_term(self.run.loot_summary[-1]) if self.run.loot_summary else "",
             "loot_key": self.run.loot_summary[-1] if self.run.loot_summary else None,
             "injury_status": self.run.injury_status},
            actor_id=history_target.char_id,
            location_id=self.run.destination if kind == "adventure_death" else self.run.origin, severity=severity,
        )
