"""Seeded world-generation proof of concept.

The generator intentionally aims for determinism and inspectability rather than
realistic geography. It provides:

- a repeatable terrain map backed by ``TerrainMap``
- extracted site candidates that future import flows can reuse
- a simple ASCII preview for tooling and review
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

from ..terrain import Site, TerrainCell, TerrainMap
from .types import SiteCandidate, generated_world_to_dict


@dataclass(slots=True)
class WorldgenConfig:
    """Configuration for deterministic PoC terrain generation."""

    width: int = 32
    height: int = 18
    seed: int = 0
    site_candidate_limit: int = 12

    def __post_init__(self) -> None:
        if not isinstance(self.width, int) or isinstance(self.width, bool) or self.width < 3:
            raise ValueError("width must be an integer >= 3")
        if not isinstance(self.height, int) or isinstance(self.height, bool) or self.height < 3:
            raise ValueError("height must be an integer >= 3")
        if not isinstance(self.site_candidate_limit, int) or isinstance(self.site_candidate_limit, bool):
            raise ValueError("site_candidate_limit must be an integer")
        if self.site_candidate_limit < 1:
            raise ValueError("site_candidate_limit must be >= 1")


@dataclass(slots=True)
class GeneratedWorld:
    """Generated terrain plus candidate metadata."""

    seed: int
    width: int
    height: int
    terrain_map: TerrainMap
    site_candidates: List[SiteCandidate] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return generated_world_to_dict(
            seed=self.seed,
            width=self.width,
            height=self.height,
            terrain_map=self.terrain_map,
            site_candidates=self.site_candidates,
        )


def _noise(seed: int, x: int, y: int, *, scale_x: float, scale_y: float, phase: float) -> float:
    return (
        0.55 * math.sin((x + seed * 0.071) * scale_x + phase)
        + 0.35 * math.cos((y - seed * 0.053) * scale_y - phase * 0.5)
        + 0.20 * math.sin((x + y) * 0.13 + seed * 0.011 + phase * 1.7)
    )


def _edge_falloff(x: int, y: int, *, width: int, height: int) -> float:
    cx = (width - 1) / 2.0
    cy = (height - 1) / 2.0
    dx = abs(x - cx) / max(cx, 1.0)
    dy = abs(y - cy) / max(cy, 1.0)
    return max(dx, dy)


def _clamp_byte(value: float) -> int:
    return max(0, min(255, int(round(value))))


def _classify_biome(*, elevation: int, moisture: int, temperature: int, near_ocean: bool) -> str:
    if elevation < 86:
        return "ocean"
    if near_ocean and elevation < 108:
        return "coast"
    if elevation > 212:
        return "mountain"
    if elevation > 180:
        return "hills"
    if temperature < 70:
        return "tundra"
    if moisture < 75 and temperature > 170:
        return "desert"
    if moisture > 175 and elevation < 150:
        return "swamp"
    if moisture > 135:
        return "forest"
    return "plains"


def _generate_cell(seed: int, x: int, y: int, *, width: int, height: int) -> TerrainCell:
    falloff = _edge_falloff(x, y, width=width, height=height)
    elevation_base = 145 + _noise(seed, x, y, scale_x=0.29, scale_y=0.31, phase=0.7) * 58
    elevation = _clamp_byte(elevation_base - falloff * 78)
    moisture = _clamp_byte(132 + _noise(seed + 17, x, y, scale_x=0.21, scale_y=0.18, phase=1.1) * 62)
    temperature = _clamp_byte(
        180
        - (y / max(height - 1, 1)) * 92
        + _noise(seed + 53, x, y, scale_x=0.17, scale_y=0.24, phase=0.4) * 28
    )
    near_ocean = falloff > 0.83 or elevation < 104
    biome = _classify_biome(
        elevation=elevation,
        moisture=moisture,
        temperature=temperature,
        near_ocean=near_ocean,
    )
    return TerrainCell(
        x=x,
        y=y,
        biome=biome,
        elevation=elevation,
        moisture=moisture,
        temperature=temperature,
    )


def _site_score(cell: TerrainCell, neighbors: Iterable[TerrainCell]) -> Tuple[int, List[str], str]:
    score = 0
    rationale: List[str] = []
    site_type = "village"
    if cell.biome in {"plains", "coast"}:
        score += 35
        rationale.append("settlement_friendly_biome")
        site_type = "city" if cell.biome == "coast" else "village"
    elif cell.biome == "forest":
        score += 24
        rationale.append("resource_rich_woodland")
        site_type = "village"
    elif cell.biome in {"hills", "mountain"}:
        score += 18
        rationale.append("defensible_high_ground")
        site_type = "fortress" if cell.biome == "mountain" else "outpost"

    if 100 <= cell.elevation <= 185:
        score += 18
        rationale.append("moderate_elevation")
    if 90 <= cell.temperature <= 190:
        score += 12
        rationale.append("temperate_climate")
    if 90 <= cell.moisture <= 190:
        score += 10
        rationale.append("stable_water_supply")

    neighbor_biomes = {neighbor.biome for neighbor in neighbors}
    if "coast" in neighbor_biomes:
        score += 12
        rationale.append("trade_water_access")
        if site_type == "city":
            site_type = "port"
    if "mountain" in neighbor_biomes and cell.biome != "mountain":
        score += 8
        rationale.append("mountain_frontier")
    if "forest" in neighbor_biomes and cell.biome == "plains":
        score += 6
        rationale.append("forest_edge_resources")

    return score, rationale, site_type


def _derive_site_candidates(terrain_map: TerrainMap, *, seed: int, limit: int) -> List[SiteCandidate]:
    rng = random.Random(seed ^ 0xA57E)
    ranked: List[Tuple[int, float, TerrainCell, List[str], str]] = []
    fallback_ranked: List[Tuple[int, float, TerrainCell, List[str], str]] = []
    for (x, y), cell in terrain_map.cells.items():
        if cell.biome in {"ocean", "swamp"}:
            continue
        neighbors = terrain_map.neighbors(x, y)
        score, rationale, site_type = _site_score(cell, neighbors)
        if score < 45:
            fallback_ranked.append((score, rng.random(), cell, rationale or ["minimum_viable_site"], site_type))
            continue
        ranked.append((score, rng.random(), cell, rationale, site_type))

    if not ranked:
        ranked = fallback_ranked
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    chosen: List[SiteCandidate] = []
    occupied: set[Tuple[int, int]] = set()
    for score, _, cell, rationale, site_type in ranked:
        if len(chosen) >= limit:
            break
        if any(abs(cell.x - ox) <= 2 and abs(cell.y - oy) <= 2 for ox, oy in occupied):
            continue
        site_id = f"generated_site_{len(chosen) + 1:02d}"
        chosen.append(
            SiteCandidate(
                site_id=site_id,
                x=cell.x,
                y=cell.y,
                site_type=site_type,
                importance=max(20, min(100, score)),
                rationale=rationale,
            )
        )
        occupied.add((cell.x, cell.y))
    return chosen


def generate_world(config: WorldgenConfig | None = None) -> GeneratedWorld:
    """Generate deterministic terrain and site candidates from *config*."""
    effective = config or WorldgenConfig()
    terrain_map = TerrainMap(width=effective.width, height=effective.height)
    for y in range(effective.height):
        for x in range(effective.width):
            terrain_map.set_cell(
                _generate_cell(
                    effective.seed,
                    x,
                    y,
                    width=effective.width,
                    height=effective.height,
                )
            )
    site_candidates = _derive_site_candidates(
        terrain_map,
        seed=effective.seed,
        limit=max(1, effective.site_candidate_limit),
    )
    return GeneratedWorld(
        seed=effective.seed,
        width=effective.width,
        height=effective.height,
        terrain_map=terrain_map,
        site_candidates=site_candidates,
    )


def build_ascii_preview(world: GeneratedWorld) -> str:
    """Render a compact ASCII preview with site overlays."""
    site_lookup = {(candidate.x, candidate.y): candidate for candidate in world.site_candidates}
    rows: List[str] = []
    for y in range(world.height):
        chars: List[str] = []
        for x in range(world.width):
            candidate = site_lookup.get((x, y))
            if candidate is not None:
                chars.append("@" if candidate.site_type in {"city", "port"} else "S")
                continue
            cell = world.terrain_map.get(x, y)
            chars.append(cell.glyph if cell is not None else "?")
        rows.append("".join(chars))
    return "\n".join(rows)


def generated_sites_as_runtime_sites(world: GeneratedWorld) -> List[Site]:
    """Project site candidates into runtime ``Site`` objects for import experiments."""
    return [
        Site(
            location_id=candidate.site_id,
            x=candidate.x,
            y=candidate.y,
            site_type=candidate.site_type,
            importance=candidate.importance,
        )
        for candidate in world.site_candidates
    ]
