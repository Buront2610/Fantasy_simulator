"""Authoring inspection helpers for setting bundles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


def setting_entry_key(name: str) -> str:
    """Return a stable inspection key for lightweight named setting entries."""
    return name.strip().lower().replace(" ", "_").replace("-", "_").replace("'", "")


@dataclass(frozen=True)
class SettingEntryInspection:
    """Typed inspection view for lightweight setting entries backed by names."""

    entry_type: str
    key: str
    display_name: str


@dataclass(frozen=True)
class SettingBundleAuthoringSummary:
    """Stable, non-UI summary for bundle inspection and swap review."""

    world_key: str
    display_name: str
    site_count: int
    route_count: int
    language_count: int
    culture_count: int = 0
    faction_count: int = 0
    glossary_count: int = 0
    language_community_count: int = 0
    resident_site_ids: List[str] = field(default_factory=list)
    capital_site_ids: List[str] = field(default_factory=list)
    culture_keys: List[str] = field(default_factory=list)
    faction_keys: List[str] = field(default_factory=list)
    glossary_keys: List[str] = field(default_factory=list)
    site_counts_by_region_type: Dict[str, int] = field(default_factory=dict)
    route_counts_by_type: Dict[str, int] = field(default_factory=dict)
    language_keys: List[str] = field(default_factory=list)
    community_keys_by_region: Dict[str, List[str]] = field(default_factory=dict)
    sites_with_native_names: List[str] = field(default_factory=list)
    site_ids_without_language_key: List[str] = field(default_factory=list)
    site_ids_without_language_community: List[str] = field(default_factory=list)
    site_ids_without_matching_language_community: List[str] = field(default_factory=list)


def named_setting_entries(entry_type: str, names: List[str]) -> List[SettingEntryInspection]:
    return [
        SettingEntryInspection(
            entry_type=entry_type,
            key=setting_entry_key(name),
            display_name=name,
        )
        for name in names
    ]


def glossary_setting_entries(glossary: List[Any]) -> List[SettingEntryInspection]:
    return [
        SettingEntryInspection(
            entry_type="glossary",
            key=setting_entry_key(entry.term),
            display_name=entry.term,
        )
        for entry in glossary
    ]


def counts_by_attr(items: List[Any], attr_name: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        value = getattr(item, attr_name)
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def community_keys_by_region(language_communities: List[Any]) -> Dict[str, List[str]]:
    mapping: Dict[str, List[str]] = {}
    for community in language_communities:
        for region_id in community.regions:
            mapping.setdefault(region_id, []).append(community.community_key)
    return {region_id: sorted(keys) for region_id, keys in sorted(mapping.items())}


def site_ids_without_language_key(site_seeds: List[Any]) -> List[str]:
    return sorted(
        seed.location_id
        for seed in site_seeds
        if not seed.language_key.strip()
    )


def site_ids_without_language_community(site_seeds: List[Any], language_communities: List[Any]) -> List[str]:
    covered_region_ids = {
        region_id
        for community in language_communities
        for region_id in community.regions
    }
    return sorted(
        seed.location_id
        for seed in site_seeds
        if seed.location_id not in covered_region_ids
    )


def site_ids_without_matching_language_community(site_seeds: List[Any], language_communities: List[Any]) -> List[str]:
    covered_language_regions = {
        (community.language_key, region_id)
        for community in language_communities
        for region_id in community.regions
    }
    return sorted(
        seed.location_id
        for seed in site_seeds
        if seed.language_key.strip()
        and (seed.language_key, seed.location_id) not in covered_language_regions
    )


def build_setting_bundle_authoring_summary(bundle: Any) -> SettingBundleAuthoringSummary:
    """Return a compact summary suitable for authoring and swap validation."""
    world = bundle.world_definition
    return SettingBundleAuthoringSummary(
        world_key=world.world_key,
        display_name=world.display_name,
        site_count=len(world.site_seeds),
        route_count=len(world.route_seeds),
        language_count=len(world.languages),
        culture_count=len(world.cultures),
        faction_count=len(world.factions),
        glossary_count=len(world.glossary),
        language_community_count=len(world.language_communities),
        resident_site_ids=world.resident_site_ids(),
        capital_site_ids=world.capital_site_ids(),
        culture_keys=sorted(entry.key for entry in world.culture_entries()),
        faction_keys=sorted(entry.key for entry in world.faction_entries()),
        glossary_keys=sorted(entry.key for entry in world.glossary_entries()),
        site_counts_by_region_type=world.site_counts_by_region_type(),
        route_counts_by_type=world.route_counts_by_type(),
        language_keys=sorted(language.language_key for language in world.languages),
        community_keys_by_region=world.community_keys_by_region(),
        sites_with_native_names=sorted(
            seed.location_id for seed in world.site_seeds if seed.native_name.strip()
        ),
        site_ids_without_language_key=world.site_ids_without_language_key(),
        site_ids_without_language_community=world.site_ids_without_language_community(),
        site_ids_without_matching_language_community=world.site_ids_without_matching_language_community(),
    )
