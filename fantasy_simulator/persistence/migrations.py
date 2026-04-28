"""Schema migration dispatcher for save data."""

from __future__ import annotations

from typing import Any, Callable, Dict

from ..content.world_data import (
    DEFAULT_LOCATIONS,
    NAME_TO_LOCATION_ID,
    fallback_location_id,
    get_location_state_defaults,
)
from .migration_context import configure_legacy_world_data
from .migration_steps import (
    migrate_v0_to_v1 as _migrate_v0_to_v1,
    migrate_v1_to_v2 as _migrate_v1_to_v2,
    migrate_v2_to_v3 as _migrate_v2_to_v3,
    migrate_v3_to_v4 as _migrate_v3_to_v4,
    migrate_v4_to_v5 as _migrate_v4_to_v5,
    migrate_v5_to_v6 as _migrate_v5_to_v6,
    migrate_v6_to_v7 as _migrate_v6_to_v7,
    migrate_v7_to_v8 as _migrate_v7_to_v8,
)

CURRENT_VERSION = 8

configure_legacy_world_data(
    default_locations=DEFAULT_LOCATIONS,
    name_to_location_id=NAME_TO_LOCATION_ID,
    fallback_location_id=fallback_location_id,
    location_state_defaults=get_location_state_defaults,
)

MIGRATIONS: Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    1: _migrate_v0_to_v1,
    2: _migrate_v1_to_v2,
    3: _migrate_v2_to_v3,
    4: _migrate_v3_to_v4,
    5: _migrate_v4_to_v5,
    6: _migrate_v5_to_v6,
    7: _migrate_v6_to_v7,
    8: _migrate_v7_to_v8,
}


def migrate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Apply all necessary migrations to bring data to CURRENT_VERSION."""
    version = data.get("schema_version", 0)
    if version > CURRENT_VERSION:
        raise ValueError(
            f"Save data has schema_version {version}, but this build only supports up to {CURRENT_VERSION}. "
            "Please upgrade the application."
        )

    for target_version in range(version + 1, CURRENT_VERSION + 1):
        data = MIGRATIONS[target_version](data)
    return data
