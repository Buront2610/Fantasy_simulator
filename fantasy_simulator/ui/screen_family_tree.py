"""Family-tree screen flow."""

from __future__ import annotations

from typing import Any

from ..character_model.family_tree import render_family_tree_lines
from .ui_context import UIContext, _default_ctx


def _show_family_tree(sim: Any, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    ctx.out.print_line()
    for line in render_family_tree_lines(sim.world):
        ctx.out.print_line(f"  {line}")
    ctx.inp.pause()
