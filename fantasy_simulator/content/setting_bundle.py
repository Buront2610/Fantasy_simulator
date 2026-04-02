"""Minimal setting bundle schema and loader for PR-I foundation work."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from .world_data import WORLD_LORE


@dataclass
class WorldDefinition:
    """Static lore metadata for a world setting bundle."""

    world_key: str
    display_name: str
    lore_text: str
    era: str = ""
    cultures: List[str] = field(default_factory=list)
    factions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "world_key": self.world_key,
            "display_name": self.display_name,
            "lore_text": self.lore_text,
            "era": self.era,
            "cultures": list(self.cultures),
            "factions": list(self.factions),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldDefinition":
        return cls(
            world_key=data["world_key"],
            display_name=data["display_name"],
            lore_text=data["lore_text"],
            era=data.get("era", ""),
            cultures=list(data.get("cultures", [])),
            factions=list(data.get("factions", [])),
        )


@dataclass
class SettingBundle:
    """Minimal serializable container for static world-definition data."""

    schema_version: int
    world_definition: WorldDefinition

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "world_definition": self.world_definition.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SettingBundle":
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            world_definition=WorldDefinition.from_dict(data["world_definition"]),
        )


def default_aethoria_bundle(
    *,
    display_name: str = "Aethoria",
    lore_text: str = WORLD_LORE,
) -> SettingBundle:
    """Return the default in-repo bundle until PR-J authors external data."""

    return SettingBundle(
        schema_version=1,
        world_definition=WorldDefinition(
            world_key="aethoria",
            display_name=display_name,
            lore_text=lore_text,
            era="Age of Embers",
        ),
    )


def load_setting_bundle(path: str | Path) -> SettingBundle:
    """Load a setting bundle from a JSON file."""

    bundle_path = Path(path)
    try:
        data = json.loads(bundle_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Setting bundle not found: {bundle_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid setting bundle JSON in {bundle_path}: {exc.msg}") from exc

    try:
        return SettingBundle.from_dict(data)
    except KeyError as exc:
        missing = exc.args[0]
        raise ValueError(f"Setting bundle {bundle_path} is missing required field: {missing}") from exc
