"""
ui_helpers.py - Display formatting and input utilities for the CLI.
"""

from __future__ import annotations

from typing import List, Optional

from .. import display_width as _display_width
from ..i18n import tr

_wcwidth = _display_width._wcwidth
_wcswidth = _display_width._wcswidth


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def bold(t: str) -> str:
    return _c(t, "1")


def red(t: str) -> str:
    return _c(t, "31")


def green(t: str) -> str:
    return _c(t, "32")


def yellow(t: str) -> str:
    return _c(t, "33")


def cyan(t: str) -> str:
    return _c(t, "36")


def dim(t: str) -> str:
    return _c(t, "2")


HEADER = r"""
  ======================================================================
    FANTASY SIMULATOR
    AETHORIA
  ======================================================================
"""


def _hr(char: str = "=",
        width: int = 62) -> str:
    return "  " + char * width


def _pause(message: str = "") -> None:
    suffix = f"  {message}\n" if message else ""
    try:
        input(dim(f"\n{suffix}  {tr('press_enter')} "))
    except EOFError:
        return


def display_width(text: str) -> int:
    old_wcwidth = _display_width._wcwidth
    old_wcswidth = _display_width._wcswidth
    try:
        _display_width._wcwidth = _wcwidth
        _display_width._wcswidth = _wcswidth
        return _display_width.display_width(text)
    finally:
        _display_width._wcwidth = old_wcwidth
        _display_width._wcswidth = old_wcswidth


def fit_display_width(text: str, width: int, suffix: str = "...") -> str:
    old_wcwidth = _display_width._wcwidth
    old_wcswidth = _display_width._wcswidth
    try:
        _display_width._wcwidth = _wcwidth
        _display_width._wcswidth = _wcswidth
        return _display_width.fit_display_width(text, width, suffix=suffix)
    finally:
        _display_width._wcwidth = old_wcwidth
        _display_width._wcswidth = old_wcswidth


def _render_menu(
    prompt: str,
    key_label_pairs: List[tuple[str, str]],
    default: Optional[str] = None,
) -> None:
    """Print menu items to stdout.  Pure rendering — no ``input()`` call.

    *key_label_pairs* is a list of ``(key, display_label)`` tuples.
    *default* is a 1-based index string (e.g. ``"1"``).
    """
    print()
    if prompt:
        print(f"  {bold(prompt)}")
    for i, (_key, label) in enumerate(key_label_pairs, 1):
        marker = green(">") if str(i) == default else " "
        print(f"  {marker} {cyan(str(i))}.  {label}")
    print()


def _read_menu_choice(
    key_label_pairs: List[tuple[str, str]],
    default: Optional[str] = None,
) -> str:
    """Read and validate a 1-based menu index, return the corresponding key.

    Pure input — assumes the menu options have already been rendered.
    """
    while True:
        hint = f" ({tr('menu_default_short')} {default})" if default else ""
        try:
            raw = input(f"  {bold(tr('your_choice'))}{hint}: ").strip()
        except EOFError:
            return _closed_input_menu_key(key_label_pairs, default)
        if not raw and default:
            raw = default
        if raw.isdigit() and 1 <= int(raw) <= len(key_label_pairs):
            return key_label_pairs[int(raw) - 1][0]
        print(red(f"  {tr('invalid_choice')}"))


def _closed_input_menu_key(
    key_label_pairs: List[tuple[str, str]],
    default: Optional[str] = None,
) -> str:
    for preferred in ("exit", "back", "return", "cancel"):
        for key, _label in key_label_pairs:
            if key == preferred:
                return key
    if default and default.isdigit() and 1 <= int(default) <= len(key_label_pairs):
        return key_label_pairs[int(default) - 1][0]
    return key_label_pairs[-1][0] if key_label_pairs else ""


# Kept for backward compatibility with external code / tests that import it.
def _choose_key(
    prompt: str,
    key_label_pairs: List[tuple[str, str]],
    default: Optional[str] = None,
) -> str:
    """Display a numbered menu and return the **key** of the selected item."""
    _render_menu(prompt, key_label_pairs, default)
    return _read_menu_choice(key_label_pairs, default)
