"""Atlas terrain and route glyph palettes."""

from __future__ import annotations

from typing import Dict, Tuple


# Terrain character palette -- 4 chars per biome for variation.
_BIOME_CHARS: Dict[str, str] = {
    "ocean": "~" * 4,
    "coast": "..`.",
    "plains": ".,',",
    "forest": "TtYf",
    "hills": "nNnh",
    "mountain": "^^/\\",
    "swamp": "%~%w",
    "desert": ":.;:",
    "tundra": "*.**",
    "river": "=~=~",
}

# Route line chars: (horizontal, vertical, diag-up, diag-down)
_ROUTE_LINE: Dict[str, Tuple[str, str, str, str]] = {
    "road": ("-", "|", "/", "\\"),
    "trail": (".", ":", ".", "."),
    "sea_lane": ("~", "~", "~", "~"),
    "mountain_pass": ("^", "^", "^", "^"),
    "river_crossing": ("=", "|", "/", "\\"),
}

# Characters that a route line may overwrite.
_TERRAIN_OVERWRITABLE = set("~.,'.TtYfnNnh^^/\\%w:.;:*=`")


def _terrain_char(biome: str, x: int, y: int) -> str:
    """Pick a varied terrain character for *biome* at canvas (x, y)."""
    chars = _BIOME_CHARS.get(biome, ".,',")
    n = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return chars[n % len(chars)]
