"""Title-screen rendering for the CLI entry point."""

from __future__ import annotations

from ..i18n import tr
from .ui_context import UIContext, _default_ctx


_TITLE_MAP = (
    r"          /\                         +----------------------+",
    r"      ___/  \___        C$====v~====D!    1000.01.01  >>>   |",
    r"     /  ^  ^   \__        \\   |   //     !  ?  *  $  m     |",
    r"     \__ T  ___ _/         T---o---?      ///// ///// ///   |",
    r"        \__   __/          v'---C!--D^    >>> >>> >>> >>>   |",
    r"           \_/                         +----------------------+",
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
    out.print_separator("=", 72)
