"""Language-facing API methods mixed into ``World``."""

from __future__ import annotations

from typing import Any, Dict, List

from . import facade as language_facade
from ..language.engine import LanguageEngine
from ..language.state import LanguageEvolutionRecord, LocationNameHistoryRecord


class WorldLanguageMixin:
    """Compatibility API surface for world language helpers."""

    @property
    def language_engine(self) -> LanguageEngine:
        return language_facade.language_engine(self)

    def naming_rules_for_identity(
        self,
        *,
        race: str | None = None,
        tribe: str | None = None,
        region: str | None = None,
    ):
        return language_facade.naming_rules_for_identity(self, race=race, tribe=tribe, region=region)

    def resolve_language_for_identity(
        self,
        *,
        race: str | None = None,
        tribe: str | None = None,
        region: str | None = None,
    ) -> str | None:
        return language_facade.resolve_language_for_identity(self, race=race, tribe=tribe, region=region)

    def describe_language_lineage(self, language_key: str) -> List[str]:
        return language_facade.describe_language_lineage(self, language_key)

    def location_endonym(self, location_id: str) -> str | None:
        return language_facade.location_endonym(self, location_id)

    def language_status(self) -> List[Dict[str, Any]]:
        return language_facade.language_status(self)

    def language_evolution_records(self, language_key: str) -> List[LanguageEvolutionRecord]:
        return language_facade.language_evolution_records(self, language_key)

    def location_name_records(self, location_id: str) -> List[LocationNameHistoryRecord]:
        return language_facade.location_name_history(self, location_id)

    def _seed_initial_location_name_history(self) -> None:
        language_facade.seed_initial_location_name_history(self)

    def _refresh_generated_endonyms(
        self,
        stale_endonyms_by_location_id: Dict[str, str] | None = None,
    ) -> None:
        language_facade.refresh_generated_endonyms(
            self,
            stale_endonyms_by_location_id=stale_endonyms_by_location_id,
        )

    def _derive_language_evolution_record(self, language_key: str, year: int) -> LanguageEvolutionRecord | None:
        return language_facade.derive_language_evolution_record(self, language_key=language_key, year=year)

    def _apply_language_evolution_record(self, record: LanguageEvolutionRecord) -> bool:
        return language_facade.apply_language_evolution_record(self, record)

    def apply_language_evolution_from_event(
        self,
        record: Any,
        *,
        language_key: str | None = None,
        cause_key: str = "",
    ) -> LanguageEvolutionRecord | None:
        return language_facade.apply_language_evolution_from_event(
            self,
            record,
            language_key=language_key,
            cause_key=cause_key,
        )

    def _maybe_evolve_languages_for_year(self, year: int) -> None:
        language_facade.maybe_evolve_languages_for_year(self, year)
