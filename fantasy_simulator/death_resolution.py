"""Shared death-resolution helpers.

Death can be reached from ordinary events, natural decline, battle, and
adventure progression.  This module keeps the durable side effects in one
place while preserving the public ``EventSystem`` compatibility methods.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .i18n import tr

if TYPE_CHECKING:
    from .character import Character
    from .world import World


def handle_death_side_effects(char: "Character", world: "World") -> None:
    """Apply idempotent side effects that follow a character death."""
    if char.spouse_id:
        spouse = world.get_character_by_id(char.spouse_id)
        if spouse and spouse.alive and spouse.spouse_id == char.char_id:
            spouse.update_relationship(char.char_id, -50)
            spouse.add_history(tr("history_lost_spouse", year=world.year, name=char.name))
            spouse.spouse_id = None


def resolve_active_adventure_for_death(char: "Character", world: "World") -> None:
    """Resolve the character's active adventure, if any, as a death outcome."""
    if char.active_adventure_id is None:
        return

    adventure_id = char.active_adventure_id
    run = world.get_adventure_by_id(adventure_id)
    if run is not None and not run.is_resolved:
        run.state = "resolved"
        run.outcome = "death"
        run.resolution_year = world.year
        run.pending_choice = None
        world.complete_adventure(adventure_id)
    char.active_adventure_id = None


def mark_character_dead(char: "Character", world: "World") -> None:
    """Apply the common world-state changes for a character death."""
    char.alive = False
    resolve_active_adventure_for_death(char, world)
    handle_death_side_effects(char, world)
