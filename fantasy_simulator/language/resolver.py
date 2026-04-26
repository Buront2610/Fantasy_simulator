"""Language community resolution service."""

from __future__ import annotations

from typing import Mapping

from ..content.setting_bundle import LanguageCommunityDefinition, LanguageDefinition, WorldDefinition


class LanguageResolver:
    """Resolve the best language for race/tribe/region selectors."""

    def __init__(
        self,
        world_definition: WorldDefinition,
        language_index: Mapping[str, LanguageDefinition],
    ) -> None:
        self._world_definition = world_definition
        self._language_index = language_index

    def resolve_language(
        self,
        *,
        race: str | None = None,
        tribe: str | None = None,
        region: str | None = None,
    ) -> LanguageDefinition | None:
        provided_selectors = {
            key: value
            for key, value in {
                "race": race,
                "tribe": tribe,
                "region": region,
            }.items()
            if value is not None
        }
        best_match: LanguageCommunityDefinition | None = None
        best_rank = (-1, -1, -1, -1)
        if provided_selectors:
            for community in self._world_definition.language_communities:
                rank = self._community_match_rank(community, provided_selectors)
                if rank is None:
                    continue
                if rank > best_rank:
                    best_rank = rank
                    best_match = community

        if best_match is not None:
            return self._language_index.get(best_match.language_key)

        lingua_francas = [
            community
            for community in self._world_definition.language_communities
            if community.is_lingua_franca
        ]
        if lingua_francas:
            lingua_franca = max(lingua_francas, key=lambda community: community.priority)
            return self._language_index.get(lingua_franca.language_key)

        if len(self._world_definition.languages) == 1:
            return self._world_definition.languages[0]
        return None

    @staticmethod
    def _community_match_rank(
        community: LanguageCommunityDefinition,
        provided_selectors: Mapping[str, str],
    ) -> tuple[int, int, int, int] | None:
        selector_values = {
            "race": list(community.races),
            "tribe": list(community.tribes),
            "region": list(community.regions),
        }
        if not any(selector_values.values()):
            return None
        matched_dimensions = 0
        extra_constraints = 0
        for selector, allowed_values in selector_values.items():
            provided_value = provided_selectors.get(selector)
            if provided_value is None:
                if allowed_values:
                    extra_constraints += 1
                continue
            if not allowed_values:
                continue
            if provided_value not in allowed_values:
                return None
            matched_dimensions += 1
        if matched_dimensions == 0:
            return None
        is_exact_match = matched_dimensions == len(provided_selectors) and extra_constraints == 0
        return (
            1 if is_exact_match else 0,
            matched_dimensions,
            -extra_constraints,
            community.priority,
        )
