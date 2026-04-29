from __future__ import annotations

from dataclasses import dataclass

import pytest

from fantasy_simulator.world_actor_index import add_adventure


@dataclass
class _Adventure:
    adventure_id: str


def test_add_adventure_rejects_duplicate_id_at_command_boundary() -> None:
    existing = _Adventure("adv_1")
    duplicate = _Adventure("adv_1")
    active_adventures = [existing]
    adventure_index = {existing.adventure_id: existing}

    with pytest.raises(ValueError, match="Duplicate adventure ID"):
        add_adventure(
            active_adventures=active_adventures,
            adventure_index=adventure_index,
            run=duplicate,
        )

    assert active_adventures == [existing]
    assert adventure_index == {"adv_1": existing}


def test_add_adventure_rejects_id_already_reserved_by_index() -> None:
    completed = _Adventure("adv_1")
    duplicate = _Adventure("adv_1")
    active_adventures: list[_Adventure] = []
    adventure_index = {completed.adventure_id: completed}

    with pytest.raises(ValueError, match="Duplicate adventure ID"):
        add_adventure(
            active_adventures=active_adventures,
            adventure_index=adventure_index,
            run=duplicate,
        )

    assert active_adventures == []
    assert adventure_index == {"adv_1": completed}
