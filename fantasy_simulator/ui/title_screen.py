"""Title-screen rendering for the CLI entry point."""

from __future__ import annotations

from ..i18n import tr
from .ui_context import UIContext, _default_ctx


def render_title_screen(ctx: UIContext | None = None) -> None:
    """Render a compact title screen before the main menu."""
    ctx = _default_ctx(ctx)
    out = ctx.out
    out.print_line()
    out.print_separator("=", 68)
    out.print_heading(f"    {tr('title_screen_name')}")
    out.print_highlighted(f"    {tr('title_screen_world')}")
    out.print_separator("-", 68)
    for key in (
        "title_screen_line_simulation",
        "title_screen_line_people",
        "title_screen_line_maps",
    ):
        out.print_dim(f"    {tr(key)}")
    out.print_separator("=", 68)
