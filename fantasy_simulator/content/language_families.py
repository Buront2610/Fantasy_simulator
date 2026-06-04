"""Language-family atlas read models for setting-bundle authoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .setting_bundle_schema import WorldDefinition


@dataclass(frozen=True)
class LanguageAtlasFamilyView:
    """One authored language family and its member languages."""

    family_key: str
    display_name: str
    proto_language_key: str = ""
    origin_region_ids: List[str] = field(default_factory=list)
    language_keys: List[str] = field(default_factory=list)
    cultural_tags: List[str] = field(default_factory=list)
    semantic_domain_tags: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class LanguageAtlasView:
    """Read model for language family coverage and grouping."""

    family_count: int
    language_count: int
    families: List[LanguageAtlasFamilyView] = field(default_factory=list)
    language_keys_without_family: List[str] = field(default_factory=list)


def build_language_atlas_view(world_definition: WorldDefinition) -> LanguageAtlasView:
    """Build a stable family -> languages projection."""
    languages_by_family: dict[str, List[str]] = {}
    languages_without_family: List[str] = []
    family_keys = {family.family_key for family in world_definition.language_families}
    for language in sorted(world_definition.languages, key=lambda item: item.language_key):
        if language.family_key and language.family_key in family_keys:
            languages_by_family.setdefault(language.family_key, []).append(language.language_key)
        else:
            languages_without_family.append(language.language_key)

    families = [
        LanguageAtlasFamilyView(
            family_key=family.family_key,
            display_name=family.display_name,
            proto_language_key=family.proto_language_key,
            origin_region_ids=list(family.origin_region_ids),
            language_keys=languages_by_family.get(family.family_key, []),
            cultural_tags=list(family.cultural_tags),
            semantic_domain_tags=list(family.semantic_domain_tags),
        )
        for family in sorted(world_definition.language_families, key=lambda item: item.family_key)
    ]
    return LanguageAtlasView(
        family_count=len(families),
        language_count=len(world_definition.languages),
        families=families,
        language_keys_without_family=languages_without_family,
    )


def language_atlas_lines(world_definition: WorldDefinition) -> List[str]:
    """Render stable CLI lines for language-family inspection."""
    view = build_language_atlas_view(world_definition)
    lines = [f"language families: {view.family_count}", f"languages: {view.language_count}"]
    for family in view.families:
        languages = ", ".join(family.language_keys) or "-"
        origins = ", ".join(family.origin_region_ids) or "-"
        proto = family.proto_language_key or "-"
        lines.append(f"{family.family_key}: {languages} | proto={proto} | origins={origins}")
    if view.language_keys_without_family:
        lines.append("languages without family: " + ", ".join(view.language_keys_without_family))
    return lines
