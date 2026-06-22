"""Combat event helpers for EventSystem."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, List

from .combat import Combatant, CombatResolution, resolve_combat
from .event_causality import pair_cause_event_ids
from .event_models import EventResult, generate_record_id
from .event_story import prefix_description_with_story_hook
from .i18n import tr

if TYPE_CHECKING:
    from .character import Character
    from .world import World


def _rival_tag_updates(winner: Combatant, loser: Combatant) -> List[Dict[str, str]]:
    winner.add_relation_tag(loser.char_id, "rival")
    loser.add_relation_tag(winner.char_id, "rival")
    return [
        {"source": winner.char_id, "target": loser.char_id, "tag": "rival"},
        {"source": loser.char_id, "target": winner.char_id, "tag": "rival"},
    ]


def _apply_battle_side_effects(resolution: CombatResolution) -> None:
    resolution.winner.apply_stat_delta(resolution.winner_gains)
    resolution.loser.apply_stat_delta(resolution.loser_losses)
    resolution.winner.update_mutual_relationship(resolution.loser, -20, delta_other=-30)


def _battle_render_metadata(
    summary_key: str,
    resolution: CombatResolution,
    story_hook_key: str,
) -> Dict[str, Any]:
    return {
        "summary_key": summary_key,
        "render_params": {
            "winner": resolution.winner.name,
            "loser": resolution.loser.name,
            "loser_injury_status": resolution.loser.injury_status,
            "story_hook_key": story_hook_key,
            "combat_log": resolution.combat_log_payload(),
        },
    }


def _battle_metadata(
    summary_key: str,
    event_source_id: str,
    cause_event_ids: List[str],
    relation_tag_updates: List[Dict[str, str]],
    resolution: CombatResolution,
    story_hook_key: str,
) -> Dict[str, Any]:
    return {
        "relation_tag_updates": relation_tag_updates,
        "record_id": event_source_id,
        "cause_event_ids": cause_event_ids,
        **_battle_render_metadata(summary_key, resolution, story_hook_key),
    }


def resolve_battle_event(
    char1: "Character",
    char2: "Character",
    world: "World",
    *,
    event_death: Any,
    rng: Any = random,
) -> EventResult:
    """Resolve a battle, including injury staging and possible fatal outcome."""
    resolution = resolve_combat(char1, char2, rng)
    _apply_battle_side_effects(resolution)

    event_source_id = generate_record_id(rng)
    cause_event_ids = pair_cause_event_ids(
        world,
        resolution.winner,
        resolution.loser,
        relation_tags=("rival",),
        event_kinds=("battle", "battle_fatal", "meeting"),
        limit=3,
    )
    relation_tag_updates = _rival_tag_updates(resolution.winner, resolution.loser)

    old_status = resolution.loser.injury_status
    resolution.loser.worsen_injury()
    loser_died = (
        resolution.loser.injury_status == "dying"
        and resolution.loser.constitution <= 5
        and rng.random() < 0.4
    )
    desc, story_hook_key = _battle_description(resolution, loser_died, old_status, rng)

    if loser_died:
        event_death(resolution.loser, world, rng=rng)
        resolution.winner.add_history(tr(
            "history_battle_fatal", year=world.year, name=resolution.loser.name,
            location=world.location_name(resolution.winner.location_id),
        ))
        return EventResult(
            description=desc,
            affected_characters=[resolution.winner.char_id, resolution.loser.char_id],
            stat_changes=_battle_stat_changes(resolution),
            event_type="battle_fatal",
            year=world.year,
            metadata=_battle_metadata(
                "events.battle_fatal.summary",
                event_source_id,
                cause_event_ids,
                relation_tag_updates,
                resolution,
                story_hook_key,
            ),
        )

    resolution.winner.add_history(tr(
        "history_battle_win", year=world.year, name=resolution.loser.name,
        location=world.location_name(resolution.winner.location_id),
    ))
    resolution.loser.add_history(tr(
        "history_battle_loss", year=world.year, name=resolution.winner.name,
        location=world.location_name(resolution.loser.location_id),
    ))
    return EventResult(
        description=desc,
        affected_characters=[resolution.winner.char_id, resolution.loser.char_id],
        stat_changes=_battle_stat_changes(resolution),
        event_type="battle",
        year=world.year,
        metadata=_battle_metadata(
            "events.battle_result.summary",
            event_source_id,
            cause_event_ids,
            relation_tag_updates,
            resolution,
            story_hook_key,
        ),
    )


def _battle_description(
    resolution: CombatResolution,
    loser_died: bool,
    old_status: str,
    rng: Any,
) -> tuple[str, str]:
    if loser_died:
        desc = tr("battle_fatal", winner=resolution.winner.name, loser=resolution.loser.name)
    else:
        desc = tr("battle_normal", winner=resolution.winner.name, loser=resolution.loser.name)
        if resolution.loser.injury_status != old_status and resolution.loser.injury_status != "none":
            desc += " " + tr(f"battle_injury_{resolution.loser.injury_status}", name=resolution.loser.name)
    return prefix_description_with_story_hook(
        "battle",
        rng,
        desc,
        winner=resolution.winner.name,
        loser=resolution.loser.name,
    )


def _battle_stat_changes(resolution: CombatResolution) -> Dict[str, Dict[str, int]]:
    return {
        resolution.winner.char_id: resolution.winner_gains,
        resolution.loser.char_id: resolution.loser_losses,
    }
