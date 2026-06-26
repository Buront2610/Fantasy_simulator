"""World event recording, indexing, projection, rendering, and data contracts."""

from __future__ import annotations

from .models import EventResult, WorldEventRecord, generate_record_id
from .rendering import EventRenderContext, render_event_record

__all__ = [
    "EventRenderContext",
    "EventResult",
    "WorldEventRecord",
    "generate_record_id",
    "render_event_record",
]
