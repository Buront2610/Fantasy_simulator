"""Helpers for attaching direct cause links between world events."""

from __future__ import annotations

from typing import Any, Iterable, Sequence


def relation_source_event_ids(character: Any, other_id: str, tags: Iterable[str]) -> list[str]:
    """Return event IDs that established selected relation tags to *other_id*."""
    sources = getattr(character, "relation_tag_sources", {})
    if not isinstance(sources, dict):
        return []
    event_ids: list[str] = []
    for tag in tags:
        raw_values = sources.get(f"{other_id}:{tag}", [])
        if not isinstance(raw_values, list):
            continue
        event_ids.extend(value for value in raw_values if isinstance(value, str) and value)
    return list(dict.fromkeys(event_ids))


def latest_pair_event_ids(
    event_records: Sequence[Any],
    actor_ids: Iterable[str],
    kinds: Iterable[str],
    *,
    limit: int = 1,
) -> list[str]:
    """Return newest event IDs whose actors include all *actor_ids* and whose kind matches."""
    required_actor_ids = {actor_id for actor_id in actor_ids if actor_id}
    allowed_kinds = set(kinds)
    if not required_actor_ids or not allowed_kinds or limit <= 0:
        return []

    found: list[str] = []
    for record in reversed(event_records):
        if getattr(record, "kind", "") not in allowed_kinds:
            continue
        record_actor_ids = set(getattr(record, "secondary_actor_ids", []))
        primary_actor_id = getattr(record, "primary_actor_id", None)
        if isinstance(primary_actor_id, str) and primary_actor_id:
            record_actor_ids.add(primary_actor_id)
        if not required_actor_ids.issubset(record_actor_ids):
            continue
        record_id = getattr(record, "record_id", "")
        if isinstance(record_id, str) and record_id:
            found.append(record_id)
            if len(found) >= limit:
                break
    return found


def pair_cause_event_ids(
    world: Any,
    char1: Any,
    char2: Any,
    *,
    relation_tags: Iterable[str] = (),
    event_kinds: Iterable[str] = (),
    limit: int = 3,
) -> list[str]:
    """Return direct cause event IDs for a new event involving two characters."""
    event_ids: list[str] = []
    event_ids.extend(relation_source_event_ids(char1, char2.char_id, relation_tags))
    event_ids.extend(relation_source_event_ids(char2, char1.char_id, relation_tags))
    event_ids.extend(
        latest_pair_event_ids(
            getattr(world, "event_records", []),
            (char1.char_id, char2.char_id),
            event_kinds,
            limit=limit,
        )
    )
    known_record_ids = {
        record_id for record in getattr(world, "event_records", [])
        for record_id in [getattr(record, "record_id", "")]
        if isinstance(record_id, str) and record_id
    }
    return [
        event_id for event_id in dict.fromkeys(event_ids)
        if event_id in known_record_ids
    ][:limit]
