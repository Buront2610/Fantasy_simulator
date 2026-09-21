"""Resolve on isolated party state, then commit state, facts and completion together."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ..adventure.itinerary import affected_location_ids

from ..adventure.results import AdventureStepResult, step_fact_result
from ..adventure.validation import validate_adventure_run_payload
from ..i18n import tr
from ..adventure.routing import capture_travel_network, validate_itinerary_references
from .adventure_travel import arrive_if_due, plan_departure, travel_step
from .adventure_schedule import prepare_scheduled_step
from .adventure_transaction import AdventureTransaction, affected_characters, clone_rng, copy_rng_state


@dataclass(frozen=True, slots=True)
class AdventureLocationView:
    id: str
    canonical_name: str
    region_type: str
    danger: int


class AdventureDraftWorld:
    """The closed world surface used by an adventure's domain decision.

    Adding a domain write requires expanding this boundary and its rollback tests;
    there is deliberately no fallback that can mutate the live World.
    """

    def __init__(self, world: Any, run: Any) -> None:
        self.year = world.year
        self.run = deepcopy(run)
        self.travel_network = capture_travel_network(world) if run.itinerary is not None else None
        self.original_characters = {member.char_id: member for member in affected_characters(world, run)}
        self.characters = {key: deepcopy(member) for key, member in self.original_characters.items()}
        self.locations = {}
        for location_id in affected_location_ids(run):
            location = world.get_location_by_id(location_id)
            if location is None:
                raise ValueError(f"Unknown adventure location: {location_id!r}")
            self.locations[location_id] = AdventureLocationView(
                location.id, location.canonical_name, location.region_type, location.danger,
            )

    def get_character_by_id(self, character_id: str) -> Any:
        return self.characters.get(character_id)

    def get_location_by_id(self, location_id: str) -> Any:
        return self.locations.get(location_id)

    def location_name(self, location_id: str) -> str:
        return self.locations[location_id].canonical_name

    def get_adventure_by_id(self, adventure_id: str) -> Any:
        if adventure_id != self.run.adventure_id:
            raise ValueError("Adventure transition cannot change another adventure")
        return self.run

    def complete_adventure(self, adventure_id: str) -> None:
        self.get_adventure_by_id(adventure_id)
        # Storage moves only after the planned facts are recorded successfully.


def _dead_leader_result(draft: AdventureDraftWorld, character: Any) -> AdventureStepResult:
    run = draft.run
    death_location = run.itinerary.current_site_id if run.itinerary is not None else run.destination
    run.pending_choice = None
    run.state, run.outcome = "resolved", "death"
    run.death_member_id, run.resolution_year = character.char_id, draft.year
    run._clear_member_adventures(draft)
    character.add_history(tr(
        "history_adventure_detail", year=draft.year,
        detail=tr("detail_adventure_died", name=character.name, destination=draft.location_name(death_location)),
    ))
    return step_fact_result(run, "adventure_death", "summary_adventure_died",
                            {"name": character.name, "destination": draft.location_name(death_location)},
                            actor_id=character.char_id, location_id=death_location, severity=5)


def apply_adventure_transition(simulator: Any, run: Any, *, choice: bool = False, option: str | None = None) -> None:
    """Prevalidate references, plan without live writes, and atomically commit one step."""
    if simulator.world.get_adventure_by_id(run.adventure_id) is not run or run.is_resolved:
        raise ValueError("Adventure must be a live unresolved run")
    validate_adventure_run_payload(run)
    validate_itinerary_references(simulator.world, run)
    draft = AdventureDraftWorld(simulator.world, run)
    character = draft.characters[run.character_id]
    rng = clone_rng(simulator.rng)
    result = _plan_step(draft, character, rng, simulator.elapsed_days + 1, choice=choice, option=option)
    validate_adventure_run_payload(draft.run)
    if result.adventure_id != run.adventure_id or result.new_state != draft.run.state:
        raise ValueError("Adventure result conflicts with its planned state")
    for fact in result.facts:
        if fact.location_id not in draft.locations:
            raise ValueError("Adventure fact refers to an unaffected location")
        if any(actor not in draft.characters for actor in (fact.primary_actor_id, *fact.secondary_actor_ids)):
            raise ValueError("Adventure fact refers to an unknown participant")
    with AdventureTransaction(simulator, run, replacing_party=True):
        run.__dict__.clear()
        run.__dict__.update(vars(draft.run))
        for actor_id, original in draft.original_characters.items():
            original.__dict__.clear()
            original.__dict__.update(vars(draft.characters[actor_id]))
        if run.itinerary is not None:
            simulator.world.mark_location_visited(run.itinerary.current_site_id)
        copy_rng_state(simulator.rng, rng)
        simulator._record_adventure_step_result(run, result)
        if run.is_resolved:
            simulator._complete_resolved_adventure(run)


def _plan_step(
    draft: AdventureDraftWorld, character: Any, rng: Any, tick: int, *, choice: bool, option: str | None,
) -> AdventureStepResult:
    blocked = arrive_if_due(draft, draft.run, tick) if character.alive else False
    scheduled_result = prepare_scheduled_step(draft.run, tick) if character.alive else None
    route_result = (travel_step(draft, draft.run, blocked=blocked)
                    if character.alive and not choice and scheduled_result is None else None)
    if scheduled_result is not None:
        result = scheduled_result
    elif route_result is not None:
        result = route_result
    elif choice:
        if not character.alive or draft.run.pending_choice is None:
            raise ValueError("Adventure choice is no longer available")
        result = draft.run.resolve_choice_result(draft, character, option=option)
    elif not character.alive:
        result = _dead_leader_result(draft, character)
    else:
        result = draft.run.step_result(character, draft, rng=rng)
    if draft.run.schedule is not None:
        draft.run.schedule.plan_next(draft.run.state, tick)
        plan_departure(draft.travel_network, draft.run, tick)
    return result
