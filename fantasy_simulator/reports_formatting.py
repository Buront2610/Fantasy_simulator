"""Backward-compatible report formatting imports."""

from __future__ import annotations

from .reports.formatting import format_monthly_report, format_yearly_report

__all__ = [
    "format_monthly_report",
    "format_yearly_report",
]
