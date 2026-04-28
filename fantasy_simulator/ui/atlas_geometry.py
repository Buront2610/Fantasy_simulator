"""Geometry helpers shared by map and atlas renderers."""

from __future__ import annotations

from typing import List, Tuple


def _bresenham(
    x0: int, y0: int, x1: int, y1: int,
) -> List[Tuple[int, int]]:
    """Integer points along a line from (x0, y0) to (x1, y1)."""
    pts: List[Tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x1 > x0 else -1
    sy = 1 if y1 > y0 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        pts.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return pts
