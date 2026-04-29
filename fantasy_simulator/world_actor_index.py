"""Character, adventure, and lightweight location lookup helpers for ``World``."""

from __future__ import annotations

from typing import Any, Callable, Iterable, List, Mapping, Protocol, Sequence, TypeVar

from .i18n import tr


class CharacterRecord(Protocol):
    char_id: str
    name: str
    location_id: str
    alive: bool


class AdventureRecord(Protocol):
    adventure_id: str


class LocationRecord(Protocol):
    id: str
    canonical_name: str
    region_type: str
    visited: bool


CharacterT = TypeVar("CharacterT", bound=CharacterRecord)
AdventureT = TypeVar("AdventureT", bound=AdventureRecord)


def default_resident_location_id(
    *,
    locations: Iterable[LocationRecord],
    location_index: Mapping[str, LocationRecord],
    location_ids_for_site_tag: Callable[[str], List[str]],
) -> str:
    """Return the best default home location for residents in this world."""
    tagged_defaults = location_ids_for_site_tag("default_resident") or location_ids_for_site_tag("capital")
    if tagged_defaults:
        return sorted(tagged_defaults)[0]

    non_dungeons = sorted(loc.id for loc in locations if loc.region_type != "dungeon")
    if non_dungeons:
        return non_dungeons[0]

    all_locations = sorted(location_index)
    if all_locations:
        return all_locations[0]

    raise ValueError("World has no locations.")


def mark_location_visited(location_index: Mapping[str, LocationRecord], location_id: str) -> None:
    """Mark a location as visited when it exists."""
    location = location_index.get(location_id)
    if location is not None:
        location.visited = True


def ensure_valid_character_locations(
    *,
    characters: Iterable[CharacterRecord],
    location_index: Mapping[str, LocationRecord],
    default_location_id: Callable[[], str],
    mark_visited: Callable[[str], None],
) -> None:
    """Repair invalid character location references against live locations."""
    character_list = list(characters)
    if not character_list:
        return
    if not location_index:
        for character in character_list:
            character.location_id = ""
        return

    fallback = default_location_id()
    for character in character_list:
        if character.location_id not in location_index:
            character.location_id = fallback
        mark_visited(character.location_id)


def add_character(
    *,
    characters: List[CharacterT],
    character_index: dict[str, CharacterT],
    location_index: Mapping[str, LocationRecord],
    locations: Iterable[LocationRecord],
    character: CharacterT,
    default_location_id: Callable[[], str],
    mark_visited: Callable[[str], None],
    rng: Any,
) -> None:
    """Add a character while maintaining the ID index and location invariants."""
    if character.location_id not in location_index:
        if not character.location_id:
            character.location_id = default_location_id()
        else:
            options = [loc.id for loc in locations if loc.region_type != "dungeon"]
            if options:
                character.location_id = rng.choice(options)
            else:
                character.location_id = default_location_id()

    if character.char_id in character_index:
        raise ValueError(
            f"Duplicate character ID: {character.char_id!r} "
            f"(existing: {character_index[character.char_id].name!r}, "
            f"new: {character.name!r})"
        )

    characters.append(character)
    character_index[character.char_id] = character
    mark_visited(character.location_id)


def rebuild_character_index(characters: Iterable[CharacterT]) -> dict[str, CharacterT]:
    """Build a character ID index and fail on duplicate IDs."""
    index: dict[str, CharacterT] = {}
    for character in characters:
        if character.char_id in index:
            raise ValueError(
                f"Duplicate character ID during rebuild: {character.char_id!r} "
                f"(existing: {index[character.char_id].name!r}, "
                f"duplicate: {character.name!r})"
            )
        index[character.char_id] = character
    return index


def remove_character(
    *,
    characters: Sequence[CharacterT],
    character_index: dict[str, CharacterT],
    char_id: str,
) -> List[CharacterT]:
    """Return the character list with one ID removed and update the index."""
    character_index.pop(char_id, None)
    return [character for character in characters if character.char_id != char_id]


def rebuild_adventure_index(
    active_adventures: Iterable[AdventureT],
    completed_adventures: Iterable[AdventureT],
) -> dict[str, AdventureT]:
    """Build an adventure ID index and fail on duplicate IDs."""
    index: dict[str, AdventureT] = {}
    for run in list(active_adventures) + list(completed_adventures):
        if run.adventure_id in index:
            raise ValueError(f"Duplicate adventure ID during rebuild: {run.adventure_id!r}")
        index[run.adventure_id] = run
    return index


def add_adventure(
    *,
    active_adventures: List[AdventureT],
    adventure_index: dict[str, AdventureT],
    run: AdventureT,
) -> None:
    """Add an active adventure and update the ID index."""
    if run.adventure_id in adventure_index:
        raise ValueError(f"Duplicate adventure ID: {run.adventure_id!r}")
    active_adventures.append(run)
    adventure_index[run.adventure_id] = run


def complete_adventure(
    *,
    active_adventures: Iterable[AdventureT],
    completed_adventures: List[AdventureT],
    adventure_id: str,
) -> List[AdventureT]:
    """Move a matching active adventure into completed adventures."""
    remaining: List[AdventureT] = []
    for run in active_adventures:
        if run.adventure_id == adventure_id:
            completed_adventures.append(run)
        else:
            remaining.append(run)
    return remaining


def location_names(locations: Iterable[LocationRecord]) -> List[str]:
    return sorted(loc.canonical_name for loc in locations)


def location_ids(locations: Iterable[LocationRecord]) -> List[str]:
    return sorted(loc.id for loc in locations)


def location_name(location_index: Mapping[str, LocationRecord], location_id: str) -> str:
    loc = location_index.get(location_id)
    if loc is not None:
        return loc.canonical_name
    return tr("unknown_location_with_id", location_id=location_id)


def characters_at_location(characters: Iterable[CharacterT], location_id: str) -> List[CharacterT]:
    return [character for character in characters if character.location_id == location_id and character.alive]
