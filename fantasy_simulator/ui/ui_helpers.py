"""
ui_helpers.py - Display formatting and input utilities for the CLI.
"""

from __future__ import annotations

import unicodedata
from typing import List, Optional

from ..i18n import tr


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
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("F", "W") else 1
    return width


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
        char_width = 2 if unicodedata.east_asian_width(char) in ("F", "W") else 1
        if unicodedata.combining(char):
            char_width = 0
        if used_width + char_width > limit:
            break
        kept.append(char)
        used_width += char_width

    clipped = "".join(kept) + suffix
    return clipped + " " * (width - display_width(clipped))


def _choose_key(
    prompt: str,
    key_label_pairs: List[tuple[str, str]],
    default: Optional[str] = None,
) -> str:
    """Display a numbered menu and return the **key** of the selected item.

    *key_label_pairs* is a list of ``(key, display_label)`` tuples.
    *default* is a 1-based index string (e.g. ``"1"``).
    This avoids locale-dependent control flow.
    """
    print()
    if prompt:
        print(f"  {bold(prompt)}")
    for i, (_key, label) in enumerate(key_label_pairs, 1):
        marker = green(">") if str(i) == default else " "
        print(f"  {marker} {cyan(str(i))}.  {label}")
    print()
    while True:
        hint = f" (default {default})" if default else ""
        raw = input(f"  {bold(tr('your_choice'))}{hint}: ").strip()
        if not raw and default:
            raw = default
        if raw.isdigit() and 1 <= int(raw) <= len(key_label_pairs):
            return key_label_pairs[int(raw) - 1][0]
        print(red(f"  {tr('invalid_choice')}"))
