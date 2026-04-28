"""Compatibility facade for setting-bundle schema, validation, and loading."""

from __future__ import annotations

from .setting_bundle_inspection import (
    SettingBundleAuthoringSummary,
    SettingEntryInspection,
    build_setting_bundle_authoring_summary,
)
from .setting_bundle_loader import (
    DEFAULT_AETHORIA_BUNDLE_PATH,
    bundle_from_dict_validated,
    default_aethoria_bundle,
    load_setting_bundle,
    validate_setting_bundle,
)
from .setting_bundle_schema import (
    CalendarDefinition,
    CalendarMonthDefinition,
    GlossaryEntryDefinition,
    JobDefinition,
    LanguageCommunityDefinition,
    LanguageDefinition,
    NamingRulesDefinition,
    RaceDefinition,
    RouteSeedDefinition,
    SettingBundle,
    SiteSeedDefinition,
    WorldDefinition,
    default_calendar_definition,
    legacy_location_id_alias,
    merge_event_impact_rule_overrides,
    merge_propagation_rule_overrides,
)

__all__ = [
    "CalendarDefinition",
    "CalendarMonthDefinition",
    "DEFAULT_AETHORIA_BUNDLE_PATH",
    "GlossaryEntryDefinition",
    "JobDefinition",
    "LanguageCommunityDefinition",
    "LanguageDefinition",
    "NamingRulesDefinition",
    "RaceDefinition",
    "RouteSeedDefinition",
    "SettingBundle",
    "SettingBundleAuthoringSummary",
    "SettingEntryInspection",
    "SiteSeedDefinition",
    "WorldDefinition",
    "build_setting_bundle_authoring_summary",
    "bundle_from_dict_validated",
    "default_aethoria_bundle",
    "default_calendar_definition",
    "legacy_location_id_alias",
    "load_setting_bundle",
    "merge_event_impact_rule_overrides",
    "merge_propagation_rule_overrides",
    "validate_setting_bundle",
]
