"""Serialization helpers for :class:`~.engine.Simulator`."""

from __future__ import annotations

import ast
import random
from typing import Any, Dict, Optional

from ..i18n import get_locale, set_locale
from ..narrative.template_history import TemplateHistory


class EnginePersistenceMixin:
    """Persist and restore simulator-owned state."""

    @staticmethod
    def _id_seed_from_seed(seed: Optional[int]) -> int:
        base_seed = 0 if seed is None else seed
        return base_seed ^ 0x5EED5EED

    @staticmethod
    def _legacy_id_seed(data: Dict[str, Any]) -> int:
        world_data = data.get("world", {})
        seed = world_data.get("year", 0)
        for count in (
            len(data.get("history", [])),
            len(world_data.get("event_records", [])),
            len(world_data.get("active_adventures", [])),
            len(world_data.get("completed_adventures", [])),
        ):
            seed = (seed * 1_000_003 + count) & ((1 << 64) - 1)
        return seed ^ 0x5EED5EED

    @staticmethod
    def _restore_rng_state(rng: random.Random, state_repr: Optional[str]) -> bool:
        if state_repr is None:
            return False
        try:
            parsed = ast.literal_eval(state_repr)
            if (
                isinstance(parsed, tuple)
                and len(parsed) == 3
                and isinstance(parsed[0], int)
                and isinstance(parsed[1], tuple)
            ):
                rng.setstate(parsed)
                return True
        except (ValueError, SyntaxError, TypeError):
            return False
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialise simulator state.

        ``event_records`` is the canonical event store by policy.
        Compatibility adapters (``history``/``event_log``) are projected at
        runtime and are no longer serialized as first-class save payload fields.
        Loader paths keep backward compatibility with older snapshots that still
        contain the legacy fields.
        """
        return {
            "world": self.world.to_dict(),
            "characters": [char.to_dict() for char in self.world.characters],
            "events_per_year": self.events_per_year,
            "adventure_steps_per_year": self.adventure_steps_per_year,
            "current_month": self.current_month,
            "current_day": self.current_day,
            "elapsed_days": self.elapsed_days,
            "start_year": self.start_year,
            "locale": get_locale(),
            "rng_state": repr(self.rng.getstate()),
            "id_rng_state": repr(self.id_rng.getstate()),
            "memorial_template_history": self.memorial_template_history.to_dict(),
            "alias_template_history": self.alias_template_history.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Rebuild a simulator from a serialised snapshot."""
        from ..character import Character
        from ..world import World

        world = World.from_dict(data["world"])
        characters = []
        for char_data in data.get("characters", []):
            character = Character.from_dict(
                char_data,
                location_resolver=world.resolve_location_id_from_name,
            )
            character.location_id = (
                world.normalize_location_id(
                    character.location_id,
                    location_name=char_data.get("location"),
                )
                or character.location_id
            )
            characters.append(character)
        world.characters = characters
        world.normalize_after_load()
        sim = cls(
            world,
            events_per_year=data.get("events_per_year", 8),
            adventure_steps_per_year=data.get("adventure_steps_per_year", 3),
        )
        set_locale(data.get("locale", get_locale()))
        sim._restore_rng_state(sim.rng, data.get("rng_state"))
        if not sim._restore_rng_state(sim.id_rng, data.get("id_rng_state")):
            sim.id_rng.seed(sim._legacy_id_seed(data))
        sim.current_month, sim.current_day = sim.world.clamp_calendar_position(
            data.get("current_month", 1),
            data.get("current_day", 1),
        )
        sim.elapsed_days = max(0, int(data.get("elapsed_days", 0)))
        sim.start_year = data.get("start_year", sim.world.year)
        sim.memorial_template_history = TemplateHistory.from_dict(
            data.get("memorial_template_history", {})
        )
        sim.alias_template_history = TemplateHistory.from_dict(
            data.get("alias_template_history", {})
        )
        return sim
