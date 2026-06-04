"""Semantic-root previews for setting-bundle authoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from ..language.naming import format_name, tidy_word
from .setting_bundle_schema import LanguageRootRealization, WorldDefinition


@dataclass(frozen=True)
class SemanticRootPreview:
    """One language's deterministic realization of selected meaning roots."""

    language_key: str
    root_keys: List[str]
    surface: str
    missing_root_keys: List[str] = field(default_factory=list)
    component_surfaces: List[str] = field(default_factory=list)


def semantic_root_realization_index(
    world_definition: WorldDefinition,
) -> dict[tuple[str, str], LanguageRootRealization]:
    """Return (language_key, root_key) -> realization lookup."""
    return {
        (realization.language_key, realization.root_key): realization
        for realization in world_definition.language_root_realizations
    }


def build_semantic_root_preview(
    world_definition: WorldDefinition,
    language_key: str,
    root_keys: List[str],
) -> SemanticRootPreview:
    """Compose a deterministic toponym-like surface from language root realizations."""
    realization_index = semantic_root_realization_index(world_definition)
    component_surfaces: List[str] = []
    missing_root_keys: List[str] = []
    for root_key in root_keys:
        realization = realization_index.get((language_key, root_key))
        if realization is None:
            missing_root_keys.append(root_key)
            continue
        component_surfaces.append(realization.surface)

    surface = format_name(tidy_word("".join(component_surfaces))) if component_surfaces else ""
    return SemanticRootPreview(
        language_key=language_key,
        root_keys=list(root_keys),
        surface=surface,
        missing_root_keys=missing_root_keys,
        component_surfaces=component_surfaces,
    )


def semantic_root_coverage_lines(world_definition: WorldDefinition, *, language_key: str | None = None) -> List[str]:
    """Return stable CLI lines describing semantic-root coverage."""
    root_count = len(world_definition.semantic_roots)
    languages = [
        language
        for language in sorted(world_definition.languages, key=lambda item: item.language_key)
        if language_key is None or language.language_key == language_key
    ]
    coverage = _root_realization_coverage_by_language(world_definition)
    lines = [f"semantic roots: {root_count}"]
    for language in languages:
        realized = coverage.get(language.language_key, 0)
        lines.append(f"{language.language_key}: {realized}/{root_count} roots")
    return lines


def _root_realization_coverage_by_language(world_definition: WorldDefinition) -> dict[str, int]:
    counts = {language.language_key: 0 for language in world_definition.languages}
    for realization in world_definition.language_root_realizations:
        if realization.language_key in counts:
            counts[realization.language_key] += 1
    return dict(sorted(counts.items()))
