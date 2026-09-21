"""Rollback boundary for the concrete objects an adventure can change."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from functools import wraps
from random import Random
from typing import Any, Literal

from ..adventure.itinerary import affected_location_ids
from .adventure_objectives import objective_participants, rescue_source_run

from ..world_event.api import WorldEventRecorderPort


def clone_rng(rng: Any) -> Any:
    if isinstance(rng, Random):
        # Random.__reduce__ calls subclass constructors without arguments. Scripted
        # RNG subclasses can require arguments, so copy native state without __init__.
        cloned = Random.__new__(type(rng))
        cloned.setstate(rng.getstate())
        cloned.__dict__.update(deepcopy(vars(rng)))
        return cloned
    return deepcopy(rng)


def copy_rng_state(target: Any, source: Any) -> None:
    if hasattr(source, "getstate") and hasattr(target, "setstate"):
        target.setstate(source.getstate())
    if hasattr(source, "__dict__"):
        target.__dict__.clear()
        target.__dict__.update(deepcopy(vars(source)))


def snapshot_rng(rng: Any) -> tuple[bool, Any]:
    native = type(rng) is Random and not (vars(rng).keys() - {"gauss_next"})
    return native, rng.getstate() if native else clone_rng(rng)


def restore_rng(rng: Any, state: tuple[bool, Any]) -> None:
    native, snapshot = state
    if native:
        rng.setstate(snapshot)
    else:
        copy_rng_state(rng, snapshot)


def restore_start_rng_on_failure(start_method: Any) -> Any:
    """Include party/destination selection draws in the start transaction."""
    @wraps(start_method)
    def start(simulator: Any, *args: Any, **kwargs: Any) -> Any:
        states = [(rng, snapshot_rng(rng)) for rng in (simulator.rng, simulator.id_rng)]
        try:
            return start_method(simulator, *args, **kwargs)
        except BaseException:
            for rng, state in states:
                restore_rng(rng, state)
            raise
    return start


def affected_characters(world: Any, run: Any) -> list[Any]:
    characters = {}
    if len(run.member_ids) != len(set(run.member_ids)):
        raise ValueError("Adventure members must be unique")
    for member_id in dict.fromkeys([run.character_id, *run.member_ids]):
        member = world.get_character_by_id(member_id)
        if member is None:
            raise ValueError(f"Unknown adventure member: {member_id!r}")
        if member.active_adventure_id not in (None, run.adventure_id):
            raise ValueError(f"Adventure member belongs to another run: {member_id!r}")
        characters[member_id] = member
    for actor in objective_participants(world, run):
        if actor is None:
            raise ValueError("Unknown source adventure participant")
        characters[actor.char_id] = actor
    for member in list(characters.values()):
        spouse = world.get_character_by_id(member.spouse_id) if member.spouse_id else None
        if spouse is not None:
            characters[spouse.char_id] = spouse
    return list(characters.values())


class AdventureTransaction:
    """A synchronous commit; exceptions restore live objects and both RNG streams.

    Character/run identities survive rollback. History records are immutable during
    adventure writes and are shallow-copied to cover retention. Read indexes are
    rebuilt only on failure, avoiding full index copies on successful steps.
    """

    def __init__(self, simulator: Any, run: Any, *, replacing_party: bool = False) -> None:
        self.sim = simulator
        self.world = simulator.world
        self.assets = self.world.assets
        source = rescue_source_run(self.world, run)
        party = [run, *([source] if source else []), *affected_characters(self.world, run)]
        # Planned commits replace every party object's attributes with isolated copies.
        # Their original containers remain untouched, so retain those for rollback.
        # Starts mutate existing containers and still need deep snapshots.
        self.objects = [(obj, dict(vars(obj)) if replacing_party else deepcopy(vars(obj))) for obj in party]
        self.objects.extend((obj, deepcopy(vars(obj))) for obj in (
            simulator.memorial_template_history, simulator.alias_template_history,
        ))
        self.locations = []
        for location_id in affected_location_ids(run, self.world):
            location = self.world.get_location_by_id(location_id)
            if location is None:
                raise ValueError(f"Unknown adventure location: {location_id!r}")
            state = {item.name: deepcopy(getattr(location, item.name)) for item in fields(location)}
            self.locations.append((location, state))
        self.recorder = WorldEventRecorderPort(self.world)
        self.event_snapshot = self.recorder.snapshot(include_index=False)
        self.lists = [(owner, name, getattr(owner, name), list(getattr(owner, name))) for owner, name in (
            (self.world, "active_adventures"), (self.world, "completed_adventures"),
            (simulator, "pending_notifications"), (simulator, "_recently_completed_adventures"),
        )]
        self.memorials = dict(self.world.memorials)
        self.adventures = dict(self.world._adventure_index)
        self.rng_states = [(rng, snapshot_rng(rng)) for rng in (simulator.rng, simulator.id_rng)]

    def __enter__(self) -> AdventureTransaction:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> Literal[False]:
        if exc_type is not None:
            self.restore()
        return False

    def restore(self) -> None:
        self.world.assets = self.assets
        for obj, state in self.objects:
            obj.__dict__.clear()
            obj.__dict__.update(state)
        for location, state in self.locations:
            for name, value in state.items():
                setattr(location, name, value)
        for owner, name, original, contents in self.lists:
            original[:] = contents
            setattr(owner, name, original)
        self.world.memorials.clear()
        self.world.memorials.update(self.memorials)
        self.world._adventure_index.clear()
        self.world._adventure_index.update(self.adventures)
        self.recorder.restore(self.event_snapshot)
        for rng, state in self.rng_states:
            restore_rng(rng, state)
