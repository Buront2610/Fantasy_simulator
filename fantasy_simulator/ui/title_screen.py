"""Title-screen rendering for the CLI entry point."""

from __future__ import annotations

from ..i18n import tr
from .ui_context import UIContext, _default_ctx


_TITLE_MAP = (
    r"      /\        . . . roads . . .        [ LIVE WORLD LOG ]",
    r"  ___/  \___       C$---v~---D!          day ticks scroll",
    r" /  ^  ^   \__       \   |   /           battles surface",
    r" \__ ruins ___/        T--o--?           causes stay readable",
)


def render_title_screen(ctx: UIContext | None = None) -> None:
    """Render a compact title screen before the main menu."""
    ctx = _default_ctx(ctx)
    out = ctx.out
    out.print_line()
    out.print_separator("=", 72)
    out.print_heading(f"    {tr('title_screen_name')}")
    out.print_highlighted(f"    {tr('title_screen_edition')}")
    out.print_separator("-", 72)
    for line in _TITLE_MAP:
        out.print_dim(f"    {line}")
    out.print_separator("-", 72)
    for key in (
        "title_screen_signal_live",
        "title_screen_signal_logs",
        "title_screen_signal_atlas",
    ):
        out.print_line(f"    {tr(key)}")
    out.print_separator("=", 72)
