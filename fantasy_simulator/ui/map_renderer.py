"""
map_renderer.py - Map data extraction and ASCII rendering.

This module decouples the *data* that a map carries (``MapCellInfo``,
``MapRenderInfo``) from the *presentation* logic that turns that data
into an ASCII grid.

Domain code (``world.py``) now only needs to call ``build_map_info()``
to produce a renderer-agnostic snapshot.  The UI layer picks the
renderer it needs — currently ``render_map_ascii()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from ..i18n import tr, tr_term
from .ui_helpers import fit_display_width

if TYPE_CHECKING:
    from ..world import World


# ------------------------------------------------------------------
# Intermediate representations
# ------------------------------------------------------------------

@dataclass
class MapCellInfo:
    """Renderer-agnostic snapshot of one map cell.

    All fields are plain values — no references to ``LocationState``
    or ``World``.  This makes the data trivially serialisable and
    testable without domain objects.

    The current ASCII renderer uses a subset of these fields.
    Additional fields (``prosperity``, ``prosperity_label``,
    ``mood``, ``mood_label``, ``rumor_heat``, ``road_condition``)
    are carried so that future renderers (Rich panels, AA maps,
    colour-coded overlays) can visualise richer world state without
    needing to touch domain code again.
    """

    location_id: str
    canonical_name: str
    region_type: str
    icon: str
    safety_label: str
    danger: int
    traffic_indicator: str
    population: int
    x: int
    y: int
    highlighted: bool = False
    # Extended fields for future renderers ---------------------------------
    prosperity: int = 50
    prosperity_label: str = ""
    mood: int = 50
    mood_label: str = ""
    rumor_heat: int = 0
    road_condition: int = 50


@dataclass
class MapRenderInfo:
    """Everything a renderer needs to draw the world map.

    ``cells`` is keyed by ``(x, y)`` grid coordinates.
    """

    world_name: str
    year: int
    width: int
    height: int
    cells: Dict[Tuple[int, int], MapCellInfo] = field(default_factory=dict)


# ------------------------------------------------------------------
# Data extraction (domain → intermediate)
# ------------------------------------------------------------------

def build_map_info(
    world: "World",
    highlight_location: Optional[str] = None,
) -> MapRenderInfo:
    """Extract a ``MapRenderInfo`` snapshot from a live ``World``.

    This is the *only* function that touches ``World`` / ``LocationState``
    attributes.  Renderers only consume the intermediate representation.
    """
    info = MapRenderInfo(
        world_name=world.name,
        year=world.year,
        width=world.width,
        height=world.height,
    )

    for (x, y), loc in world.grid.items():
        is_highlight = (
            highlight_location is not None
            and (loc.id == highlight_location or loc.canonical_name == highlight_location)
        )
        population = len(world.get_characters_at_location(loc.id))
        info.cells[(x, y)] = MapCellInfo(
            location_id=loc.id,
            canonical_name=loc.canonical_name,
            region_type=loc.region_type,
            icon="*" if is_highlight else loc.icon,
            safety_label=loc.safety_label,
            danger=loc.danger,
            traffic_indicator=loc.traffic_indicator,
            population=population,
            x=x,
            y=y,
            highlighted=is_highlight,
            prosperity=loc.prosperity,
            prosperity_label=loc.prosperity_label,
            mood=loc.mood,
            mood_label=loc.mood_label,
            rumor_heat=loc.rumor_heat,
            road_condition=loc.road_condition,
        )
    return info


# ------------------------------------------------------------------
# ASCII renderer (intermediate → string)
# ------------------------------------------------------------------

def _fit(text: str, width: int) -> str:
    """Shorthand for ``fit_display_width`` inside the renderer."""
    return fit_display_width(text, width)


def render_map_ascii(info: MapRenderInfo) -> str:
    """Render a ``MapRenderInfo`` as a stable ASCII grid.

    The output format is identical to the legacy ``World.render_map()``
    so that callers see no visual change.
    """
    cell_width = 20
    inner_width = info.width * cell_width + (info.width - 1)
    border = "  +" + "-" * inner_width + "+"
    header = f" {tr('map_title')}: {info.world_name} | {tr('map_year')}: {info.year}"
    lines: List[str] = [
        border,
        f"  |{_fit(header, inner_width)}|",
        border,
    ]

    for y in range(info.height):
        row_names: List[str] = []
        row_types: List[str] = []
        row_safety: List[str] = []
        row_danger: List[str] = []
        row_traffic: List[str] = []
        row_pops: List[str] = []

        for x in range(info.width):
            cell = info.cells.get((x, y))
            if cell is None:
                blank = " " * cell_width
                row_names.append(_fit(" ? ???", cell_width))
                row_types.append(blank)
                row_safety.append(blank)
                row_danger.append(blank)
                row_traffic.append(blank)
                row_pops.append(blank)
                continue

            region_name = tr_term(cell.region_type)
            row_names.append(_fit(f" {cell.icon} {cell.canonical_name}", cell_width))
            row_types.append(_fit(f" {tr('map_type')}: {region_name}", cell_width))
            row_safety.append(_fit(f" {tr('map_safety')}: {cell.safety_label}", cell_width))
            row_danger.append(_fit(f" {tr('map_danger')}: {cell.danger:>3}", cell_width))
            row_traffic.append(_fit(f" {tr('map_traffic')}: {cell.traffic_indicator}", cell_width))
            row_pops.append(_fit(f" {tr('map_population')}: {cell.population}", cell_width))

        lines.append("  |" + "|".join(row_names) + "|")
        lines.append("  |" + "|".join(row_types) + "|")
        lines.append("  |" + "|".join(row_safety) + "|")
        lines.append("  |" + "|".join(row_danger) + "|")
        lines.append("  |" + "|".join(row_traffic) + "|")
        lines.append("  |" + "|".join(row_pops) + "|")
        lines.append(border)

    return "\n".join(lines)
