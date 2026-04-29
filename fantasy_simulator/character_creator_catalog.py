"""Bundle catalog selection helpers for character creation."""

from __future__ import annotations

from typing import Dict, List

from .character_templates import supported_template_names
from .content.setting_bundle import SettingBundle


class CharacterCreatorCatalogMixin:
    setting_bundle: SettingBundle | None

    def _default_bundle(self) -> SettingBundle:
        raise NotImplementedError

    def _effective_bundle(self) -> SettingBundle:
        raise NotImplementedError

    @staticmethod
    def _supports_aethoria_projection_fallback(bundle: SettingBundle) -> bool:
        """Return whether empty race/job lists may fall back to Aethoria defaults."""
        return bundle.world_definition.world_key == "aethoria"

    @property
    def race_entries(self) -> List[tuple[str, str, Dict[str, int]]]:
        bundle = self._effective_bundle()
        races = bundle.world_definition.races
        if not races and self._supports_aethoria_projection_fallback(bundle):
            races = self._default_bundle().world_definition.races
        return [
            (race.name, race.description, dict(race.stat_bonuses))
            for race in races
        ]

    @property
    def job_entries(self) -> List[tuple[str, str, List[str]]]:
        bundle = self._effective_bundle()
        jobs = bundle.world_definition.jobs
        if not jobs and self._supports_aethoria_projection_fallback(bundle):
            jobs = self._default_bundle().world_definition.jobs
        return [
            (job.name, job.description, list(job.primary_skills))
            for job in jobs
        ]

    @property
    def location_entries(self) -> List[tuple[str, str, str, List[str]]]:
        """Return site seeds as authoring-friendly region/origin options."""
        bundle = self._effective_bundle()
        return [
            (seed.location_id, seed.name, seed.region_type, list(seed.tags))
            for seed in bundle.world_definition.site_seeds
        ]

    def _require_race_and_job_entries(
        self,
    ) -> tuple[List[tuple[str, str, Dict[str, int]]], List[tuple[str, str, List[str]]]]:
        race_entries = self.race_entries
        job_entries = self.job_entries
        if not race_entries:
            raise ValueError("Setting bundle must define at least one race for character creation")
        if not job_entries:
            raise ValueError("Setting bundle must define at least one job for character creation")
        return race_entries, job_entries

    def _supports_aethoria_templates(self) -> bool:
        return bool(self.list_templates())

    def list_templates(self) -> List[str]:
        """Return templates supported by the current creator context."""
        race_names = {race_name for race_name, _race_desc, _bonuses in self.race_entries}
        job_names = {job_name for job_name, _job_desc, _skills in self.job_entries}
        world = self._effective_bundle().world_definition
        return supported_template_names(
            world_key=world.world_key,
            has_explicit_race_or_job_data=bool(world.races or world.jobs),
            race_names=race_names,
            job_names=job_names,
            using_default_bundle=self.setting_bundle is None,
        )

    def _race_entries_for_context(
        self,
        *,
        tribe: str | None = None,
        region: str | None = None,
    ) -> List[tuple[str, str, Dict[str, int]]]:
        """Prefer region/tribe-authored race pools when bundle communities specify them."""
        race_entries = self.race_entries
        if not race_entries or (tribe is None and region is None):
            return race_entries

        bundle = self._effective_bundle()
        communities = bundle.world_definition.language_communities
        matching_communities = [
            community
            for community in communities
            if (
                (region is not None and region in community.regions)
                or (tribe is not None and tribe in community.tribes)
            )
            and community.races
        ]
        if not matching_communities:
            return race_entries

        matching_communities.sort(key=lambda community: (-community.priority, community.community_key))
        allowed_races = {
            race_name
            for community in matching_communities
            for race_name in community.races
        }
        filtered = [entry for entry in race_entries if entry[0] in allowed_races]
        return filtered or race_entries
