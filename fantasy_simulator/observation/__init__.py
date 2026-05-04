"""Headless read-model projections for world observation."""

from .location_history_projection import (
    LocationControlHistoryEntry,
    LocationHistoryProjection,
    LocationRenameHistoryEntry,
    build_location_history_projection,
)
from .route_status_projection import (
    RouteStatusHistoryEntry,
    RouteStatusProjection,
    build_route_status_projection,
)
from .era_timeline_projection import (
    EraTimelineEntry,
    EraTimelineProjection,
    build_era_timeline_projection,
)
from .war_map_projection import (
    OccupationEntry,
    WarMapEventEntry,
    WarMapProjection,
    build_war_map_projection,
)
from .world_change_report_projection import (
    WorldChangeCategoryCount,
    WorldChangeReportEntry,
    WorldChangeReportProjection,
    build_world_change_report_projection,
)

__all__ = [
    "EraTimelineEntry",
    "EraTimelineProjection",
    "LocationControlHistoryEntry",
    "LocationHistoryProjection",
    "LocationRenameHistoryEntry",
    "OccupationEntry",
    "RouteStatusHistoryEntry",
    "RouteStatusProjection",
    "WarMapEventEntry",
    "WarMapProjection",
    "WorldChangeCategoryCount",
    "WorldChangeReportEntry",
    "WorldChangeReportProjection",
    "build_era_timeline_projection",
    "build_location_history_projection",
    "build_route_status_projection",
    "build_war_map_projection",
    "build_world_change_report_projection",
]
