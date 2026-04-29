"""Compatibility facade for CLI screen functions.

The concrete screen flows live in focused ``screen_*`` modules.  This
module keeps the historical import path stable for callers and tests.
"""

from __future__ import annotations

from .screen_adventures import (  # noqa: F401
    _party_display_names as _party_display_names,
    _resolve_pending_adventure_choice as _resolve_pending_adventure_choice,
    _show_adventure_details as _show_adventure_details,
    _show_adventure_summaries as _show_adventure_summaries,
)
from .screen_history import (  # noqa: F401
    _month_season_hint as _month_season_hint,
    _show_location_history as _show_location_history,
    _show_monthly_report as _show_monthly_report,
    _show_single_story as _show_single_story,
)
from .screen_input import (  # noqa: F401
    _get_numeric_choice as _get_numeric_choice,
    _read_bounded_int as _read_bounded_int,
)
from .screen_language import _select_language as _select_language  # noqa: F401
from .screen_lore import (  # noqa: F401
    _build_default_language_status as _build_default_language_status,
    screen_world_lore as screen_world_lore,
)
from .screen_map import (  # noqa: F401
    _build_detail_memory_payload as _build_detail_memory_payload,
    _build_detail_observation_payload as _build_detail_observation_payload,
    _build_region_memory_payloads as _build_region_memory_payloads,
    _region_drill_loop as _region_drill_loop,
    _render_location_detail_for_location as _render_location_detail_for_location,
    _render_region_map_for_location as _render_region_map_for_location,
    _show_detail_for_location as _show_detail_for_location,
    _show_world_map as _show_world_map,
    render_world_map_views_for_location as render_world_map_views_for_location,
)
from .screen_persistence import (  # noqa: F401
    _load_simulation_snapshot as _load_simulation_snapshot,
    _save_simulation_snapshot as _save_simulation_snapshot,
)
from .screen_results import _show_results as _show_results  # noqa: F401
from .screen_roster import _show_roster as _show_roster  # noqa: F401
from .screen_setup import (  # noqa: F401
    screen_custom_simulation as screen_custom_simulation,
    screen_new_simulation as screen_new_simulation,
)
from .screen_simulation import (  # noqa: F401
    _advance_auto as _advance_auto,
    _advance_simulation as _advance_simulation,
    _build_default_world as _build_default_world,
    _run_simulation as _run_simulation,
)
