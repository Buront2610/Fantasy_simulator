"""Site marker, overlay, and label placement for atlas canvases."""

from __future__ import annotations

from typing import Dict, List, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .map_renderer import MapCellInfo, MapRenderInfo


# Site marker varies by traffic band:
#   high traffic = 'O' (hub), medium = '@', low = 'o'.
_SITE_MARKERS: Dict[str, str] = {"high": "O", "medium": "@", "low": "o"}
_SITE_MARKER = "@"


def _overlay_suffix(cell: "MapCellInfo") -> str:
    """Compact overlay markers for a site cell.

    Markers: ``!`` high danger, ``$`` high traffic, ``?`` high rumor,
    ``m`` memorial, ``a`` alias, ``+`` recent death.
    """
    parts: List[str] = []
    if cell.danger_band == "high":
        parts.append("!")
    if cell.traffic_band == "high":
        parts.append("$")
    if cell.rumor_heat_band == "high":
        parts.append("?")
    if cell.has_memorial:
        parts.append("m")
    if cell.has_alias:
        parts.append("a")
    if cell.recent_death_site:
        parts.append("+")
    return "".join(parts)


def _place_labels(
    canvas: List[List[str]],
    info: "MapRenderInfo",
    site_atlas: Dict[str, Tuple[int, int]],
    w: int,
    h: int,
    *,
    place_names: bool = True,
) -> Set[str]:
    """Place site markers and name labels on the canvas.

    Site marker glyph varies by traffic band: ``O`` hub (high),
    ``@`` normal (medium), ``o`` quiet (low).  High-rumor sites
    get a ``?`` halo in unoccupied adjacent cells.
    """
    occupied: Set[Tuple[int, int]] = {
        (ax, ay)
        for ax, ay in site_atlas.values()
        if 0 <= ay < h and 0 <= ax < w
    }
    labeled_ids: Set[str] = set()

    cells_sorted = sorted(
        info.cells.values(),
        key=lambda c: -c.site_importance,
    )

    for cell in cells_sorted:
        pos = site_atlas.get(cell.location_id)
        if not pos:
            continue
        ax, ay = pos

        marker = _SITE_MARKERS.get(cell.traffic_band, _SITE_MARKER)
        if 0 <= ay < h and 0 <= ax < w:
            canvas[ay][ax] = marker

        if not place_names:
            continue

        name = cell.canonical_name
        if len(name) > 14:
            name = name[:13] + "."
        ov = _overlay_suffix(cell)
        label = f"{name}[{ov}]" if ov else name

        candidates = [
            (ax + 1, ay),
            (ax - len(label), ay),
            (ax + 1, ay + 1),
            (ax + 1, ay - 1),
        ]
        for lx, ly in candidates:
            if lx < 0 or ly < 0 or ly >= h or lx + len(label) > w:
                continue
            if any((lx + i, ly) in occupied for i in range(len(label))):
                continue
            for i, ch in enumerate(label):
                canvas[ly][lx + i] = ch
                occupied.add((lx + i, ly))
            labeled_ids.add(cell.location_id)
            break

    for cell in info.cells.values():
        if cell.rumor_heat_band != "high":
            continue
        pos = site_atlas.get(cell.location_id)
        if not pos:
            continue
        ax, ay = pos
        for dy2, dx2 in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = ax + dx2, ay + dy2
            if 0 <= ny < h and 0 <= nx < w and (nx, ny) not in occupied:
                canvas[ny][nx] = "?"
                occupied.add((nx, ny))

    return labeled_ids
