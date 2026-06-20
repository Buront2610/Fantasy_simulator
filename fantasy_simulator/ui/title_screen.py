"""Title-screen rendering for the CLI entry point."""

from __future__ import annotations

from ..i18n import tr
from .ui_context import UIContext, _default_ctx


_TITLE_SCENE = (
    r"    .----------------------------------------------------------------.",
    r"    |        /\              /\                 +----------------+    |",
    r"    |    ___/  \___     ____/  \__     C$======|1000.01.01  >>> |    |",
    r"    |   /  ^  ^    \___/   ^  ^  \__    \\     | ! ? * $ m  >>> |    |",
    r"    |   \__ T  ___      T   ___    /     \\    | ///// ///// >> |    |",
    r"    |      \__/   \___   __/   \__/   v~==o====| >>> >>> >>> >>> |    |",
    r"    |          D!=====C!---T---D^       \\      +----------------+    |",
    r"    |             \\       |     \\       ?---v'---C$---m---D!         |",
    r"    '----------------------------------------------------------------'",
)


def render_title_screen(ctx: UIContext | None = None) -> None:
    """Render a compact title screen before the main menu."""
    ctx = _default_ctx(ctx)
    out = ctx.out
    out.print_line()
    out.print_separator("=", 76)
    wordmark = (
        f"    .====================[ {tr('title_screen_name')} ]====================.",
        r"    ||\\                                                          //||",
        f"    || \\\\          {tr('title_screen_edition')}                         // ||",
        r"    ||  \\______________________________________________________//  ||",
        r"    '================================================================'",
    )
    for index, line in enumerate(wordmark):
        if index == 0:
            out.print_heading(line)
        else:
            out.print_highlighted(line)
    out.print_separator("-", 76)
    for line in _TITLE_SCENE:
        out.print_dim(f"    {line}")
    out.print_separator("=", 76)
