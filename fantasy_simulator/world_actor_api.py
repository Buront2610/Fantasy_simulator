"""Actor and load-normalization methods for :class:`fantasy_simulator.world.World`."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, List, Optional

from .world_actor_index import (
    add_adventure as add_adventure_to_index,
    add_character as add_character_to_index,
    characters_at_location,
    complete_adventure as complete_adventure_in_index,
    default_resident_location_id,
    ensure_valid_character_locations as ensure_valid_character_locations_in_index,
    mark_location_visited as mark_location_visited_in_index,
    rebuild_adventure_index as build_adventure_index,
    rebuild_character_index,
    remove_character as remove_character_from_index,
)
from .world_load_normalizer import (
    ensure_unique_event_record_ids,
    normalize_after_load as normalize_loaded_world_state,
    rebuild_recent_event_ids,
)
from .world_reference_repair import backfill_watched_actor_tags

if TYPE_CHECKING:
    from .adventure import AdventureRun
    from .character import Character


class WorldActorMixin:
    def _location_ids_for_site_tag(self, tag: str) -> List[str]:
        """Return in-bounds location_ids for bundle site seeds carrying *tag*."""
        return [
            seed.location_id
            for seed in self._setting_bundle.world_definition.site_seeds
            if tag in seed.tags and seed.location_id in self._location_id_index
        ]

    def _default_resident_location_id(self) -> str:
        return default_resident_location_id(
            locations=self.grid.values(),
            location_index=self._location_id_index,
            location_ids_for_site_tag=self._location_ids_for_site_tag,
        )

    def mark_location_visited(self, location_id: str) -> None:
        """Mark a location as visited when it is meaningfully occupied or reached."""
        mark_location_visited_in_index(self._location_id_index, location_id)

    def ensure_valid_character_locations(self) -> None:
        """Repair invalid location references after loading legacy data."""
        ensure_valid_character_locations_in_index(
            characters=self.characters,
            location_index=self._location_id_index,
            default_location_id=self._default_resident_location_id,
            mark_visited=self.mark_location_visited,
        )

    def add_character(self, character: Character, rng: Any = random) -> None:
        add_character_to_index(
            characters=self.characters,
            character_index=self._char_index,
            location_index=self._location_id_index,
            locations=self.grid.values(),
            character=character,
            default_location_id=self._default_resident_location_id,
            mark_visited=self.mark_location_visited,
            rng=rng,
        )

    def rebuild_char_index(self) -> None:
        """Rebuild the character ID index after external mutations."""
        self._char_index = rebuild_character_index(self.characters)

    def remove_character(self, char_id: str) -> None:
        self.characters = remove_character_from_index(
            characters=self.characters,
            character_index=self._char_index,
            char_id=char_id,
        )

    def get_character_by_id(self, char_id: str) -> Optional[Character]:
        return self._char_index.get(char_id)

    def get_characters_at_location(self, location_id: str) -> List[Character]:
        return characters_at_location(self.characters, location_id)

    def get_adventure_by_id(self, adventure_id: str) -> Optional[AdventureRun]:
        return self._adventure_index.get(adventure_id)

    def rebuild_adventure_index(self) -> None:
        """Rebuild the adventure ID index after loading or external mutations."""
        self._adventure_index = build_adventure_index(
            self.active_adventures,
            self.completed_adventures,
        )

    def rebuild_recent_event_ids(self) -> None:
        """Rebuild derived per-location recent_event_ids from structured event records."""
        rebuild_recent_event_ids(
            locations=self.grid.values(),
            location_index=self._location_id_index,
            event_records=self.event_records,
        )

    def _ensure_unique_event_record_ids(self) -> None:
        """Fail fast when canonical history contains duplicate record IDs."""
        ensure_unique_event_record_ids(self.event_records)

    def normalize_after_load(self) -> None:
        """Rebuild derived indexes and repair invariants after deserialization."""
        normalize_loaded_world_state(
            event_records=self.event_records,
            repair_location_references=self._repair_location_references,
            rebuild_char_index=self.rebuild_char_index,
            backfill_watched_actor_tags=self._backfill_watched_actor_tags_after_load,
            ensure_valid_character_locations=self.ensure_valid_character_locations,
            rebuild_adventure_index=self.rebuild_adventure_index,
            rebuild_recent_event_ids_fn=self.rebuild_recent_event_ids,
            rebuild_location_memorial_ids_fn=self._rebuild_location_memorial_ids,
            rebuild_compatibility_event_log=self.rebuild_compatibility_event_log,
        )

    def _backfill_watched_actor_tags_after_load(self) -> None:
        """Freeze watched-actor report context for older untagged canonical records."""
        watched_actor_ids = {
            character.char_id
            for character in self.characters
            if character.favorite or character.spotlighted or character.playable
        }
        backfill_watched_actor_tags(
            event_records=self.event_records,
            watched_actor_ids=watched_actor_ids,
            watched_actor_tag_prefix=self.WATCHED_ACTOR_TAG_PREFIX,
            inferred_tag=self.WATCHED_ACTOR_INFERRED_TAG,
        )

    def add_adventure(self, run: AdventureRun) -> None:
        add_adventure_to_index(
            active_adventures=self.active_adventures,
            adventure_index=self._adventure_index,
            run=run,
        )

    def complete_adventure(self, adventure_id: str) -> None:
        self.active_adventures = complete_adventure_in_index(
            active_adventures=self.active_adventures,
            completed_adventures=self.completed_adventures,
            adventure_id=adventure_id,
        )
