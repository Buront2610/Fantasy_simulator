"""Serializable world-generation types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..terrain import TerrainMap


@dataclass(slots=True)
class SiteCandidate:
    """A generated site suggestion derived from terrain heuristics."""

    site_id: str
    x: int
    y: int
    site_type: str
    importance: int = 50
    rationale: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "site_id": self.site_id,
            "x": self.x,
            "y": self.y,
            "site_type": self.site_type,
            "importance": self.importance,
            "rationale": list(self.rationale),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SiteCandidate":
        return cls(
            site_id=str(data.get("site_id", "")),
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            site_type=str(data.get("site_type", "city")),
            importance=max(0, min(100, int(data.get("importance", 50)))),
            rationale=[str(item) for item in data.get("rationale", [])],
        )


def generated_world_to_dict(
    *,
    seed: int,
    width: int,
    height: int,
    terrain_map: TerrainMap,
    site_candidates: List[SiteCandidate],
) -> Dict[str, Any]:
    """Serialize a generated-world snapshot."""
    return {
        "seed": int(seed),
        "width": int(width),
        "height": int(height),
        "terrain_map": terrain_map.to_dict(),
        "site_candidates": [candidate.to_dict() for candidate in site_candidates],
    }
