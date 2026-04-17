"""Shared seeded-world and snapshot helpers for acceptance-style harness tests."""

from __future__ import annotations

import random

from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.world import World


def build_seeded_world(seed: int, n_chars: int = 6) -> World:
    """Build a seeded world with a stable non-dungeon roster spread."""
    rng = random.Random(seed)
    world = World()
    creator = CharacterCreator()
    location_ids = [loc.id for loc in world.grid.values() if loc.region_type != "dungeon"]
    for _ in range(n_chars):
        char = creator.create_random(rng=rng)
        char.location_id = rng.choice(location_ids)
        world.add_character(char)
    return world


def content_lines(text: str) -> list[str]:
    """Drop separators and blank lines so snapshot assertions stay intent-focused."""
    content: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if set(stripped) <= {"="}:
            continue
        if stripped.startswith("+") and set(stripped) <= {"+", "-"}:
            continue
        content.append(line)
    return content
