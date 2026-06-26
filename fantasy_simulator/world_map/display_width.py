"""Terminal display-width helpers shared by UI and compatibility renderers."""

from __future__ import annotations

import unicodedata
from importlib import import_module
from typing import Any, List

try:
    _wcwidth_module = import_module("wcwidth")
except ImportError:  # pragma: no cover - depends on optional ui extra
    _wcwidth: Any = None
    _wcswidth: Any = None
else:
    _wcwidth = getattr(_wcwidth_module, "wcwidth")
    _wcswidth = getattr(_wcwidth_module, "wcswidth")


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
