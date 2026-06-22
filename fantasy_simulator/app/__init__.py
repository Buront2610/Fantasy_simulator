"""Headless application service contracts for external UI adapters."""

from .contracts import AppCommandResult, EventSummaryView, WorldDashboardSnapshot
from .service import FantasyAppService

__all__ = [
    "AppCommandResult",
    "EventSummaryView",
    "FantasyAppService",
    "WorldDashboardSnapshot",
]
