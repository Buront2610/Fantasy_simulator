"""Compatibility exports for setting-bundle schema definitions."""

from __future__ import annotations

from .setting_bundle_schema_calendar import (
    CalendarDefinition,
    CalendarMonthDefinition,
    default_calendar_definition,
)
from .setting_bundle_schema_core import (
    GlossaryEntryDefinition,
    JobDefinition,
    NamingRulesDefinition,
    RaceDefinition,
    RouteSeedDefinition,
    SiteSeedDefinition,
    _bool_payload,
    _copy_rule_overrides,
    _string_list_payload,
    bool_payload,
    copy_rule_overrides,
    legacy_location_id_alias,
    merge_event_impact_rule_overrides,
    merge_propagation_rule_overrides,
    string_list_payload,
)
from .setting_bundle_schema_language import (
    LanguageCommunityDefinition,
    LanguageDefinition,
)
from .setting_bundle_schema_world import SettingBundle, WorldDefinition

__all__ = [
    "CalendarDefinition",
    "CalendarMonthDefinition",
    "GlossaryEntryDefinition",
    "JobDefinition",
    "LanguageCommunityDefinition",
    "LanguageDefinition",
    "NamingRulesDefinition",
    "RaceDefinition",
    "RouteSeedDefinition",
    "SettingBundle",
    "SiteSeedDefinition",
    "WorldDefinition",
    "_bool_payload",
    "_copy_rule_overrides",
    "_string_list_payload",
    "bool_payload",
    "copy_rule_overrides",
    "default_calendar_definition",
    "legacy_location_id_alias",
    "merge_event_impact_rule_overrides",
    "merge_propagation_rule_overrides",
    "string_list_payload",
]
