"""Location-reference repair and normalization helpers for ``World``.

This module is intentionally orchestration-oriented:
- it coordinates where normalization should be applied
- it does not define core location-validity rules itself

Domain rules (e.g., what makes a location valid) remain in ``World`` and the
resolver callback injected by the caller.
"""

from __future__ import annotations

from typing import Callable, Iterable, Mapping, MutableSequence, Protocol

from .event_models import WorldEventRecord
from .world_event_record_updates import event_record_with_added_tags, event_record_with_normalized_location_references


class CharacterLocationReference(Protocol):
    location_id: str


class RumorLocationReference(Protocol):
    source_location_id: str | None


class AdventureLocationReference(Protocol):
    origin: str
    destination: str


class LocationReferenceResolver(Protocol):
    def __call__(
        self,
        location_id: str | None,
        *,
        required: bool = False,
        fallback_location_id: str | None = None,
    ) -> str | None:
        ...


def repair_world_location_references(
    *,
    characters: Iterable[CharacterLocationReference],
    event_records: MutableSequence[WorldEventRecord],
    rumors: Iterable[RumorLocationReference],
    rumor_archive: Iterable[RumorLocationReference],
    active_adventures: Iterable[AdventureLocationReference],
    completed_adventures: Iterable[AdventureLocationReference],
    memorials: Mapping[str, CharacterLocationReference],
    repair_location_reference: LocationReferenceResolver,
    fallback_location_id: str | None,
) -> None:
    """Repair all persisted location-backed references against the live world."""
    for character in characters:
        character.location_id = (
            repair_location_reference(
                character.location_id,
                required=True,
                fallback_location_id=fallback_location_id,
            )
            or ""
        )

    for index, record in enumerate(event_records):
        event_records[index] = event_record_with_normalized_location_references(
            record,
            repair_location_reference,
        )

    for rumor in rumors:
        rumor.source_location_id = repair_location_reference(rumor.source_location_id)

    for rumor in rumor_archive:
        rumor.source_location_id = repair_location_reference(rumor.source_location_id)

    for run in active_adventures:
        run.origin = (
            repair_location_reference(
                run.origin,
                required=True,
                fallback_location_id=fallback_location_id,
            )
            or ""
        )
        run.destination = (
            repair_location_reference(
                run.destination,
                required=True,
                fallback_location_id=fallback_location_id,
            )
            or ""
        )

    for run in completed_adventures:
        run.origin = (
            repair_location_reference(
                run.origin,
                required=True,
                fallback_location_id=fallback_location_id,
            )
            or ""
        )
        run.destination = (
            repair_location_reference(
                run.destination,
                required=True,
                fallback_location_id=fallback_location_id,
            )
            or ""
        )

    for memorial in memorials.values():
        memorial.location_id = (
            repair_location_reference(
                memorial.location_id,
                required=True,
                fallback_location_id=fallback_location_id,
            )
            or ""
        )


def normalize_world_references_after_structure_change(
    *,
    repair_location_references: Callable[[], None],
    rebuild_location_memorial_ids: Callable[[], None],
    rebuild_char_index: Callable[[], None],
    ensure_valid_character_locations: Callable[[], None],
    rebuild_adventure_index: Callable[[], None],
    rebuild_recent_event_ids: Callable[[], None],
    rebuild_compatibility_event_log: Callable[[], None],
    has_event_records: bool,
) -> None:
    """Rebuild derived indexes after the world structure changes."""
    repair_location_references()
    rebuild_location_memorial_ids()
    rebuild_char_index()
    ensure_valid_character_locations()
    rebuild_adventure_index()
    rebuild_recent_event_ids()
    if has_event_records:
        rebuild_compatibility_event_log()


def backfill_watched_actor_tags(
    *,
    event_records: MutableSequence[WorldEventRecord],
    watched_actor_ids: set[str],
    watched_actor_tag_prefix: str,
    inferred_tag: str,
) -> None:
    """Stamp watched-actor tags onto older canonical records once after load."""
    if not watched_actor_ids:
        return

    for index, record in enumerate(event_records):
        if any(tag.startswith(watched_actor_tag_prefix) for tag in record.tags):
            continue
        actor_ids = [record.primary_actor_id] + list(record.secondary_actor_ids)
        watched_tags = [
            f"{watched_actor_tag_prefix}{actor_id}"
            for actor_id in actor_ids
            if actor_id and actor_id in watched_actor_ids
        ]
        if watched_tags:
            event_records[index] = event_record_with_added_tags(record, [*watched_tags, inferred_tag])
