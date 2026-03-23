"""Notification density evaluation for the Simulator (design §8).

Separates internal simulation events from player-visible alerts using
configurable thresholds.
"""

from __future__ import annotations

from typing import Any, Dict

from ..events import WorldEventRecord


class NotificationMixin:
    """Mixin providing notification threshold logic for the Simulator.

    Expected attributes on *self* (provided by ``engine.Simulator``):
    - ``world``: the World instance
    """

    NOTIFICATION_THRESHOLDS: Dict[str, Any] = {
        "favorite_any": True,
        "spotlight_serious": True,
        "rumor_high_heat": 70,
    }

    def should_notify(self, record: WorldEventRecord) -> bool:
        """Determine if an event record should trigger a player notification.

        Applies notification density thresholds (§8 of implementation plan)
        to separate internal simulation events from player-visible alerts.
        """
        thresholds = self.NOTIFICATION_THRESHOLDS

        # Always notify for major events (severity >= 4)
        if record.severity >= 4:
            return True

        # Check favorite characters
        if thresholds.get("favorite_any"):
            for char in self.world.characters:
                if not char.favorite:
                    continue
                if (record.primary_actor_id == char.char_id
                        or char.char_id in record.secondary_actor_ids):
                    return True

        # Check spotlighted characters (severity >= 3)
        if thresholds.get("spotlight_serious"):
            for char in self.world.characters:
                if not char.spotlighted:
                    continue
                if record.severity >= 3 and (
                    record.primary_actor_id == char.char_id
                    or char.char_id in record.secondary_actor_ids
                ):
                    return True

        # Check location rumor_heat threshold
        heat_threshold = thresholds.get("rumor_high_heat", 0)
        if heat_threshold and record.location_id:
            loc = self.world.get_location_by_id(record.location_id)
            if loc is not None and loc.rumor_heat >= heat_threshold:
                return True

        return False
