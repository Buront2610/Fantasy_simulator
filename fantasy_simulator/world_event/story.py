"""Story hook helpers for generated world events."""

from __future__ import annotations

import random
from hashlib import blake2s
from typing import Any

from ..i18n import tr


_STORY_HOOK_KEYS: dict[str, tuple[str, ...]] = {
    "battle": (
        "event_story_battle_old_grudge",
        "event_story_battle_public_challenge",
        "event_story_battle_route_dispute",
    ),
    "discovery": (
        "event_story_discovery_rumor",
        "event_story_discovery_map",
        "event_story_discovery_omen",
    ),
    "journey": (
        "event_story_journey_request",
        "event_story_journey_weather",
        "event_story_journey_missing_caravan",
    ),
    "meeting": (
        "event_story_meeting_shared_task",
        "event_story_meeting_market_tension",
        "event_story_meeting_old_story",
    ),
    "skill_training": (
        "event_story_training_deadline",
        "event_story_training_rival",
        "event_story_training_failed_attempt",
    ),
}


def choose_story_hook_key(event_type: str, rng: Any = random, **params: Any) -> str:
    """Choose a narrative hook key for a generated event."""
    keys = _STORY_HOOK_KEYS.get(event_type, ())
    if not keys:
        return ""
    seed = "|".join([event_type, *(f"{key}={params[key]}" for key in sorted(params))])
    digest = blake2s(seed.encode("utf-8"), digest_size=2).digest()
    return keys[int.from_bytes(digest, "big") % len(keys)]


def render_story_hook(story_hook_key: str, **params: Any) -> str:
    """Render a story hook, returning an empty string for missing keys."""
    if not story_hook_key:
        return ""
    rendered = tr(story_hook_key, **params)
    return "" if rendered == story_hook_key else rendered


def prefix_description_with_story_hook(
    event_type: str,
    rng: Any,
    description: str,
    **params: Any,
) -> tuple[str, str]:
    """Return a generated description prefixed with a chosen story hook."""
    story_hook_key = choose_story_hook_key(event_type, rng, **params)
    story_hook = render_story_hook(story_hook_key, **params)
    if not story_hook:
        return description, story_hook_key
    return f"{story_hook} {description}", story_hook_key
