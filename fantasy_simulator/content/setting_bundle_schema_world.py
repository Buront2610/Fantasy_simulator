"""World and bundle container schema definitions for setting bundles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .setting_bundle_inspection import (
    SettingEntryInspection,
    community_keys_by_region as inspect_community_keys_by_region,
    counts_by_attr,
    glossary_setting_entries,
    named_setting_entries,
    site_ids_without_language_community as inspect_site_ids_without_language_community,
    site_ids_without_language_key as inspect_site_ids_without_language_key,
    site_ids_without_matching_language_community as inspect_site_ids_without_matching_language_community,
)
from .setting_bundle_schema_calendar import CalendarDefinition, default_calendar_definition
from .setting_bundle_schema_core import (
    GlossaryEntryDefinition,
    JobDefinition,
    NamingRulesDefinition,
    RaceDefinition,
    RouteSeedDefinition,
    SiteSeedDefinition,
    copy_rule_overrides,
    string_list_payload,
)
from .setting_bundle_schema_language import LanguageCommunityDefinition, LanguageDefinition


@dataclass
class WorldDefinition:
    """Static lore metadata for a world setting bundle."""

    world_key: str
    display_name: str
    lore_text: str
    era: str = ""
    cultures: List[str] = field(default_factory=list)
    factions: List[str] = field(default_factory=list)
    glossary: List[GlossaryEntryDefinition] = field(default_factory=list)
    calendar: CalendarDefinition = field(default_factory=lambda: default_calendar_definition())
    races: List[RaceDefinition] = field(default_factory=list)
    jobs: List[JobDefinition] = field(default_factory=list)
    site_seeds: List[SiteSeedDefinition] = field(default_factory=list)
    route_seeds: List[RouteSeedDefinition] = field(default_factory=list)
    naming_rules: NamingRulesDefinition = field(default_factory=NamingRulesDefinition)
    languages: List[LanguageDefinition] = field(default_factory=list)
    language_communities: List[LanguageCommunityDefinition] = field(default_factory=list)
    event_impact_rules: Dict[str, Dict[str, int]] = field(default_factory=dict)
    propagation_rules: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def site_seed_index(self) -> Dict[str, SiteSeedDefinition]:
        """Return location_id -> site seed lookup for authoring helpers."""
        return {seed.location_id: seed for seed in self.site_seeds}

    def site_seed_by_id(self, location_id: str) -> SiteSeedDefinition | None:
        """Return the site seed for a given location id, if present."""
        return self.site_seed_index().get(location_id)

    def race_lifespan_years(self, race_name: str) -> int | None:
        """Return the authored lifespan for a race, if the bundle defines one."""
        for race in self.races:
            if race.name == race_name:
                return race.lifespan_years
        return None

    def resident_site_ids(self) -> List[str]:
        """Return site ids tagged as reasonable resident defaults."""
        return [
            seed.location_id
            for seed in self.site_seeds
            if "default_resident" in seed.tags
        ]

    def capital_site_ids(self) -> List[str]:
        """Return site ids tagged as capitals."""
        return [
            seed.location_id
            for seed in self.site_seeds
            if "capital" in seed.tags
        ]

    def culture_entries(self) -> List[SettingEntryInspection]:
        """Return typed culture inspection entries while preserving legacy storage."""
        return named_setting_entries("culture", self.cultures)

    def faction_entries(self) -> List[SettingEntryInspection]:
        """Return typed faction inspection entries while preserving legacy storage."""
        return named_setting_entries("faction", self.factions)

    def glossary_entries(self) -> List[SettingEntryInspection]:
        """Return typed glossary inspection entries while preserving authored terms."""
        return glossary_setting_entries(self.glossary)

    def site_counts_by_region_type(self) -> Dict[str, int]:
        """Return a stable region-type breakdown for authoring inspection."""
        return counts_by_attr(self.site_seeds, "region_type")

    def route_counts_by_type(self) -> Dict[str, int]:
        """Return a stable route-type breakdown for authoring inspection."""
        return counts_by_attr(self.route_seeds, "route_type")

    def community_keys_by_region(self) -> Dict[str, List[str]]:
        """Return region -> community keys mapping for bundle swap review."""
        return inspect_community_keys_by_region(self.language_communities)

    def site_ids_without_language_key(self) -> List[str]:
        """Return site ids that have no primary authored language."""
        return inspect_site_ids_without_language_key(self.site_seeds)

    def site_ids_without_language_community(self) -> List[str]:
        """Return site ids not covered by any regional language community."""
        return inspect_site_ids_without_language_community(self.site_seeds, self.language_communities)

    def site_ids_without_matching_language_community(self) -> List[str]:
        """Return site ids without a regional community for their primary language."""
        return inspect_site_ids_without_matching_language_community(self.site_seeds, self.language_communities)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "world_key": self.world_key,
            "display_name": self.display_name,
            "lore_text": self.lore_text,
            "era": self.era,
            "cultures": list(self.cultures),
            "factions": list(self.factions),
            "glossary": [entry.to_dict() for entry in self.glossary],
            "calendar": self.calendar.to_dict(),
            "races": [race.to_dict() for race in self.races],
            "jobs": [job.to_dict() for job in self.jobs],
            "site_seeds": [seed.to_dict() for seed in self.site_seeds],
            "route_seeds": [seed.to_dict() for seed in self.route_seeds],
            "naming_rules": self.naming_rules.to_dict(),
            "languages": [language.to_dict() for language in self.languages],
            "language_communities": [community.to_dict() for community in self.language_communities],
            "event_impact_rules": {
                kind: {attr: int(delta) for attr, delta in deltas.items()}
                for kind, deltas in self.event_impact_rules.items()
            },
            "propagation_rules": {
                kind: {attr: value for attr, value in deltas.items()}
                for kind, deltas in self.propagation_rules.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldDefinition":
        calendar = CalendarDefinition.from_dict(
            data.get("calendar", default_calendar_definition().to_dict())
        )
        return cls(
            world_key=data["world_key"],
            display_name=data["display_name"],
            lore_text=data["lore_text"],
            era=data.get("era", ""),
            cultures=string_list_payload(data.get("cultures", []), field_name="cultures"),
            factions=string_list_payload(data.get("factions", []), field_name="factions"),
            glossary=[
                GlossaryEntryDefinition.from_dict(item)
                for item in data.get("glossary", [])
            ],
            calendar=calendar,
            races=[
                RaceDefinition.from_dict(item)
                for item in data.get("races", [])
            ],
            jobs=[
                JobDefinition.from_dict(item)
                for item in data.get("jobs", [])
            ],
            site_seeds=[
                SiteSeedDefinition.from_dict(item)
                for item in data.get("site_seeds", [])
            ],
            route_seeds=[
                RouteSeedDefinition.from_dict(item)
                for item in data.get("route_seeds", [])
            ],
            naming_rules=NamingRulesDefinition.from_dict(data.get("naming_rules", {})),
            languages=[
                LanguageDefinition.from_dict(item)
                for item in data.get("languages", [])
            ],
            language_communities=[
                LanguageCommunityDefinition.from_dict(item)
                for item in data.get("language_communities", [])
            ],
            event_impact_rules=copy_rule_overrides(
                data.get("event_impact_rules", {}),
                field_name="world_definition.event_impact_rules",
            ),
            propagation_rules=copy_rule_overrides(
                data.get("propagation_rules", {}),
                field_name="world_definition.propagation_rules",
            ),
        )


@dataclass
class SettingBundle:
    """Serializable container for static world-definition data."""

    schema_version: int
    world_definition: WorldDefinition

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "world_definition": self.world_definition.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SettingBundle":
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            world_definition=WorldDefinition.from_dict(data["world_definition"]),
        )
