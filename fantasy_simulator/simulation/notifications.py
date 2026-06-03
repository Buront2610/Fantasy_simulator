"""Notification density evaluation for the Simulator (design §8).

Separates internal simulation events from player-visible alerts using
configurable thresholds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Set

from ..events import WorldEventRecord

if TYPE_CHECKING:
    from ..world import World


def _record_actor_ids(record: WorldEventRecord) -> Set[str]:
    """Return actor ids from canonical fields plus semantic render metadata."""
    actor_ids = set(record.secondary_actor_ids)
    if record.primary_actor_id:
        actor_ids.add(record.primary_actor_id)
    render_actor_ids = record.render_params.get("actor_ids", [])
    if isinstance(render_actor_ids, list):
        actor_ids.update(actor_id for actor_id in render_actor_ids if isinstance(actor_id, str))
    return actor_ids


class NotificationMixin:
    """Mixin providing notification threshold logic for the Simulator.

    Expected attributes on *self* (provided by ``engine.Simulator``):
    - ``world``: the World instance
    """

    NOTIFICATION_THRESHOLDS: Dict[str, Any] = {
        "favorite_any": True,
        "spotlight_serious": True,
        "rumor_high_heat": 70,
        "world_change": True,
    }

    if TYPE_CHECKING:
        world: World

    def should_notify(self, record: WorldEventRecord) -> bool:
        """Determine if an event record should trigger a player notification.

        Applies notification density thresholds (§8 of implementation plan)
        to separate internal simulation events from player-visible alerts.
        """
        thresholds = self.NOTIFICATION_THRESHOLDS

        # Always notify for major events (severity >= 4)
        if record.severity >= 4:
            return True

        if thresholds.get("world_change") and "world_change" in record.tags:
            return True

        actor_ids = _record_actor_ids(record)
        for char in self.world.characters:
            if char.char_id not in actor_ids:
                continue
            if thresholds.get("favorite_any") and char.favorite:
                return True
            if thresholds.get("spotlight_serious") and record.severity >= 3 and char.spotlighted:
                return True

        # Check location rumor_heat threshold
        heat_threshold = thresholds.get("rumor_high_heat", 0)
        if heat_threshold and record.location_id:
            loc = self.world.get_location_by_id(record.location_id)
            if loc is not None and loc.rumor_heat >= heat_threshold:
                return True

        return False
