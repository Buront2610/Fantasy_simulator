"""
main.py - Entry point for the Fantasy Simulator CLI.

Run with: python main.py

Display helpers  -> ui_helpers.py
Screen functions -> screens.py
"""

from __future__ import annotations

import sys

from i18n import set_locale, tr
from screens import (
    _load_simulation_snapshot,
    _select_language,
    _show_results,
    screen_custom_simulation,
    screen_new_simulation,
    screen_world_lore,
)
from ui_helpers import HEADER, _choose, _hr, bold, yellow


def main() -> None:
    set_locale("ja")
    print(yellow(HEADER))

    while True:
        print("\n" + _hr("="))
        print(bold(f"  {tr('main_menu')}"))
        print(_hr("="))
        choice = _choose(
            tr("main_menu_prompt"),
            [
                tr("start_new_sim"),
                tr("create_custom_sim"),
                tr("load_saved_sim"),
                tr("read_world_lore"),
                tr("language_menu"),
                tr("exit"),
            ],
            default="1",
        )

        if choice == tr("start_new_sim"):
            screen_new_simulation()
        elif choice == tr("create_custom_sim"):
            screen_custom_simulation()
        elif choice == tr("load_saved_sim"):
            sim = _load_simulation_snapshot()
            if sim is not None:
                _show_results(sim)
        elif choice == tr("read_world_lore"):
            screen_world_lore()
        elif choice == tr("language_menu"):
            _select_language()
        else:
            print(f"\n  {bold(yellow(tr('farewell')))}\n")
            sys.exit(0)


if __name__ == "__main__":
    main()
