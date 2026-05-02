"""Combat event helpers for EventSystem."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, List

from .event_models import EventResult, generate_record_id
from .i18n import tr

if TYPE_CHECKING:
    from .character import Character
    from .world import World


def _rival_tag_updates(winner: "Character", loser: "Character") -> List[Dict[str, str]]:
    winner.add_relation_tag(loser.char_id, "rival")
    loser.add_relation_tag(winner.char_id, "rival")
    return [
        {"source": winner.char_id, "target": loser.char_id, "tag": "rival"},
        {"source": loser.char_id, "target": winner.char_id, "tag": "rival"},
    ]


def resolve_battle_event(
    char1: "Character",
    char2: "Character",
    world: "World",
    *,
    event_death: Any,
    rng: Any = random,
) -> EventResult:
    """Resolve a battle, including injury staging and possible fatal outcome."""
    power1 = char1.combat_power + rng.randint(0, 30)
    power2 = char2.combat_power + rng.randint(0, 30)
    winner, loser = (char1, char2) if power1 >= power2 else (char2, char1)

    winner_gains = {"strength": rng.randint(1, 3), "constitution": rng.randint(0, 2)}
    loser_losses = {"constitution": -rng.randint(2, 8), "strength": -rng.randint(0, 3)}
    winner.apply_stat_delta(winner_gains)
    loser.apply_stat_delta(loser_losses)
    winner.update_mutual_relationship(loser, -20, delta_other=-30)

    event_source_id = generate_record_id(rng)
    relation_tag_updates = _rival_tag_updates(winner, loser)

    old_status = loser.injury_status
    loser.worsen_injury()
    loser_died = loser.injury_status == "dying" and loser.constitution <= 5 and rng.random() < 0.4

    def _render_metadata(summary_key: str) -> Dict[str, Any]:
        return {
            "summary_key": summary_key,
            "render_params": {
                "winner": winner.name,
                "loser": loser.name,
                "loser_injury_status": loser.injury_status,
            },
        }

    if loser_died:
        event_death(loser, world, rng=rng)
        desc = tr("battle_fatal", winner=winner.name, loser=loser.name)
        winner.add_history(tr(
            "history_battle_fatal", year=world.year, name=loser.name,
            location=world.location_name(winner.location_id),
        ))
        return EventResult(
            description=desc,
            affected_characters=[winner.char_id, loser.char_id],
            stat_changes={winner.char_id: winner_gains, loser.char_id: loser_losses},
            event_type="battle_fatal",
            year=world.year,
            metadata={
                "relation_tag_updates": relation_tag_updates,
                "record_id": event_source_id,
                **_render_metadata("events.battle_fatal.summary"),
            },
        )

    injury_key = f"battle_injury_{loser.injury_status}"
    desc = tr("battle_normal", winner=winner.name, loser=loser.name)
    if loser.injury_status != old_status and loser.injury_status != "none":
        desc += " " + tr(injury_key, name=loser.name)
    winner.add_history(tr(
        "history_battle_win", year=world.year, name=loser.name,
        location=world.location_name(winner.location_id),
    ))
    loser.add_history(tr(
        "history_battle_loss", year=world.year, name=winner.name,
        location=world.location_name(loser.location_id),
    ))
    return EventResult(
        description=desc,
        affected_characters=[winner.char_id, loser.char_id],
        stat_changes={winner.char_id: winner_gains, loser.char_id: loser_losses},
        event_type="battle",
        year=world.year,
        metadata={
            "relation_tag_updates": relation_tag_updates,
            "record_id": event_source_id,
            **_render_metadata("events.battle_result.summary"),
        },
    )
