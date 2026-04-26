"""
ui_helpers.py - Display formatting and input utilities for the CLI.
"""

from __future__ import annotations

import unicodedata
from typing import Any, List, Optional

from ..i18n import tr

try:
    from wcwidth import wcwidth as _imported_wcwidth
    from wcwidth import wcswidth as _imported_wcswidth
except ImportError:  # pragma: no cover - depends on optional ui extra
    _wcwidth: Any = None
    _wcswidth: Any = None
else:
    _wcwidth = _imported_wcwidth
    _wcswidth = _imported_wcswidth


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
    input(dim(f"\n{suffix}  {tr('press_enter')} "))


def display_width(text: str) -> int:
    if _wcswidth is not None:
        width = _wcswidth(text)
        return max(width, 0)

    width = 0
    for char in text:
        width += _char_display_width(char)
    return width


def _char_display_width(char: str) -> int:
    if _wcwidth is not None:
        return max(_wcwidth(char), 0)
    return _fallback_char_display_width(char)


def _fallback_char_display_width(char: str) -> int:
    if unicodedata.combining(char):
        return 0
    return 2 if unicodedata.east_asian_width(char) in ("F", "W") else 1


def fit_display_width(text: str, width: int, suffix: str = "...") -> str:
    """Pad or truncate text to a target terminal display width."""
    if width <= 0:
        return ""
    current_width = display_width(text)
    if current_width <= width:
        return text + " " * (width - current_width)

    suffix_width = display_width(suffix)
    if suffix_width >= width:
        suffix = ""
        suffix_width = 0

    kept: List[str] = []
    used_width = 0
    limit = width - suffix_width
    for char in text:
        char_width = _char_display_width(char)
        if used_width + char_width > limit:
            break
        kept.append(char)
        used_width += char_width

    clipped = "".join(kept) + suffix
    return clipped + " " * (width - display_width(clipped))


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
        hint = f" (default {default})" if default else ""
        raw = input(f"  {bold(tr('your_choice'))}{hint}: ").strip()
        if not raw and default:
            raw = default
        if raw.isdigit() and 1 <= int(raw) <= len(key_label_pairs):
            return key_label_pairs[int(raw) - 1][0]
        print(red(f"  {tr('invalid_choice')}"))


# Kept for backward compatibility with external code / tests that import it.
def _choose_key(
    prompt: str,
    key_label_pairs: List[tuple[str, str]],
    default: Optional[str] = None,
) -> str:
    """Display a numbered menu and return the **key** of the selected item."""
    _render_menu(prompt, key_label_pairs, default)
    return _read_menu_choice(key_label_pairs, default)
