"""
fantasy_simulator/main.py - CLI entry point logic for the Fantasy Simulator.

Display helpers  -> ui/ui_helpers.py
Screen functions -> ui/screens.py
UI context       -> ui/ui_context.py
"""

from __future__ import annotations

import sys

from .i18n import set_locale, tr
from .ui.screens import (
    _load_simulation_snapshot,
    _select_language,
    _show_results,
    screen_custom_simulation,
    screen_new_simulation,
    screen_world_lore,
)
from .ui.ui_helpers import HEADER, bold, yellow
from .ui.ui_context import UIContext, _default_ctx


def main(ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out
    inp = ctx.inp

    set_locale("ja")
    out.print_line(yellow(HEADER))

    while True:
        out.print_line()
        out.print_separator("=")
        out.print_heading(f"  {tr('main_menu')}")
        out.print_separator("=")
        choice = inp.choose_key(
            tr("main_menu_prompt"),
            [
                ("start_new_sim", tr("start_new_sim")),
                ("create_custom_sim", tr("create_custom_sim")),
                ("load_saved_sim", tr("load_saved_sim")),
                ("read_world_lore", tr("read_world_lore")),
                ("language_menu", tr("language_menu")),
                ("exit", tr("exit")),
            ],
            default="1",
        )

        if choice == "start_new_sim":
            screen_new_simulation(ctx=ctx)
        elif choice == "create_custom_sim":
            screen_custom_simulation(ctx=ctx)
        elif choice == "load_saved_sim":
            sim = _load_simulation_snapshot(ctx=ctx)
            if sim is not None:
                _show_results(sim, ctx=ctx)
        elif choice == "read_world_lore":
            screen_world_lore(ctx=ctx)
        elif choice == "language_menu":
            _select_language(ctx=ctx)
        else:
            out.print_line(f"\n  {bold(yellow(tr('farewell')))}\n")
            sys.exit(0)
