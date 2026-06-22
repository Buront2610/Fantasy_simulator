"""Title-screen rendering for the CLI entry point."""

from __future__ import annotations

from .ui_context import UIContext, _default_ctx


_TITLE_LOGO = (
    r" ____|           |                      ___| _)                 |       |",
    r" |    _` | __ \  __|  _` |  __| |   | \___ \  | __ `__ \  |   | |  _` | __|  _ \   __|",
    r" __| (   | |   | |   (   |\__ \ |   |       | | |   |   | |   | | (   | |   (   | |",
    r"_|  \__,_|_|  _|\__|\__,_|____/\__, | _____/ _|_|  _|  _|\__,_|_|\__,_|\__|\___/ _|",
    r"                               ____/",
)

_SUBTITLE_LOGO = (
    r"    _        _   _                _         ___  _                              _",
    r"   / \   ___| |_| |__   ___  _ __(_) __ _  / _ \| |__  ___  ___ _ ____   ____ _| |_ ___  _ __",
    r"  / _ \ / _ \ __| '_ \ / _ \| '__| |/ _` |/ /_\/ '_ \/ __|/ _ \ '__\ \ / / _` | __/ _ \| '__|",
    r" / ___ \  __/ |_| | | | (_) | |  | | (_| / /_\\| |_) \__ \  __/ |   \ V / (_| | || (_) | |",
    r"/_/   \_\___|\__|_| |_|\___/|_|  |_|\__,_\____/|_.__/|___/\___|_|    \_/ \__,_|\__\___/|_|",
    r"                                                                                       |___/",
)

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
    out.print_separator("=", 104)
    for line in _TITLE_LOGO:
        out.print_heading(f"  {line}")
    out.print_separator("-", 104)
    for line in _SUBTITLE_LOGO:
        out.print_highlighted(f"  {line}")
    out.print_separator("-", 104)
    for line in _TITLE_SCENE:
        out.print_dim(f"                    {line}")
    out.print_separator("=", 104)
