"""Shared input helpers for CLI screen flows."""

from __future__ import annotations

from typing import Optional

from ..i18n import tr
from .ui_context import UIContext, _default_ctx


def _get_numeric_choice(prompt: str, count: int, ctx: UIContext | None = None) -> Optional[int]:
    """Prompt for a 1-based index and return a 0-based index, or None."""
    ctx = _default_ctx(ctx)
    raw = ctx.inp.read_line(prompt).strip()
    if not raw:
        return None
    if not raw.isdigit():
        ctx.out.print_warning(f"  {tr('invalid_input')}")
        return None
    idx = int(raw) - 1
    if not (0 <= idx < count):
        ctx.out.print_warning(f"  {tr('invalid_input')}")
        return None
    return idx


def _read_bounded_int(
    prompt: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
    ctx: UIContext | None = None,
) -> int:
    """Read an integer response, falling back to default and clamping to bounds."""
    ctx = _default_ctx(ctx)
    raw = ctx.inp.read_line(prompt).strip()
    value = int(raw) if raw.isdigit() else default
    return max(minimum, min(maximum, value))
