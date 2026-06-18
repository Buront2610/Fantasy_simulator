"""Family-tree screen flow."""

from __future__ import annotations

from ..family_tree import render_family_tree_lines
from ..simulator import Simulator
from .ui_context import UIContext, _default_ctx


def _show_family_tree(sim: Simulator, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    ctx.out.print_line()
    for line in render_family_tree_lines(sim.world):
        ctx.out.print_line(f"  {line}")
    ctx.inp.pause()
