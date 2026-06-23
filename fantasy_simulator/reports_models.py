"""Backward-compatible report view-model imports."""

from __future__ import annotations

from .reports.models import (
    CharacterReportEntry,
    LocationReportEntry,
    MonthlyReport,
    RumorReportEntry,
    WorldChangeReportLine,
    YearlyReport,
)

__all__ = [
    "CharacterReportEntry",
    "LocationReportEntry",
    "RumorReportEntry",
    "WorldChangeReportLine",
    "MonthlyReport",
    "YearlyReport",
]
