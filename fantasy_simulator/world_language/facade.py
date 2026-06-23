"""World-object facade for language helpers."""

from __future__ import annotations

from typing import Any, Dict, List

from ..language.engine import LanguageEngine
from ..language.state import LanguageEvolutionRecord, LocationNameHistoryRecord
from . import (
    advance_world_languages_for_year,
    apply_language_evolution_from_event as apply_event_language_evolution,
    apply_evolution_record,
    build_language_engine,
    derive_evolution_record,
    evolution_records_for_language,
    language_status as build_language_status,
    location_name_history_for_location as filter_location_name_history,
    location_endonym as resolve_location_endonym,
    refresh_world_generated_endonyms,
    resolve_language_display_name,
    seed_initial_location_name_history as seed_initial_names,
)


def language_engine(world: Any) -> LanguageEngine:
    """Return the cached language engine for a world aggregate."""
    if world._language_engine is None:
        world._language_engine = build_language_engine(
            world._setting_bundle.world_definition,
            world._language_runtime_states,
        )
    return world._language_engine


def naming_rules_for_identity(
    world: Any,
    *,
    race: str | None = None,
    tribe: str | None = None,
    region: str | None = None,
):
    """Resolve naming rules through the world's language engine."""
    return world.language_engine.naming_rules_for_identity(race=race, tribe=tribe, region=region)


def resolve_language_for_identity(
    world: Any,
    *,
    race: str | None = None,
    tribe: str | None = None,
    region: str | None = None,
) -> str | None:
    """Resolve a display-facing language name for an identity selector."""
    return resolve_language_display_name(
        world.language_engine,
        race=race,
        tribe=tribe,
        region=region,
    )


def describe_language_lineage(world: Any, language_key: str) -> List[str]:
    """Describe a language lineage from the world's language engine."""
    return world.language_engine.describe_language_lineage(language_key)


def location_endonym(world: Any, location_id: str) -> str | None:
    """Resolve a native/generated location name for the active world bundle."""
    return resolve_location_endonym(
        world._setting_bundle.world_definition,
        world.language_engine,
        location_id,
    )


def language_status(world: Any) -> List[Dict[str, Any]]:
    """Return UI-facing language status summaries."""
    return build_language_status(
        world._setting_bundle.world_definition,
        world.language_engine,
        world.language_evolution_history,
    )


def language_evolution_records(world: Any, language_key: str) -> List[LanguageEvolutionRecord]:
    """Filter world language evolution history to one language."""
    return evolution_records_for_language(world.language_evolution_history, language_key)


def location_name_history(world: Any, location_id: str) -> List[LocationNameHistoryRecord]:
    """Return durable local-name history entries for one location."""
    return filter_location_name_history(world.location_name_history, location_id)


def seed_initial_location_name_history(world: Any) -> None:
    """Persist initial generated/native local names for the current world grid."""
    seed_initial_names(world)


def refresh_generated_endonyms(
    world: Any,
    *,
    stale_endonyms_by_location_id: Dict[str, str] | None = None,
) -> None:
    """Refresh generated location endonyms for the world."""
    refresh_world_generated_endonyms(
        world,
        stale_endonyms_by_location_id=stale_endonyms_by_location_id,
    )


def derive_language_evolution_record(
    world: Any,
    *,
    language_key: str,
    year: int,
) -> LanguageEvolutionRecord | None:
    """Derive the next evolution record for one language."""
    return derive_evolution_record(
        world.language_engine,
        language_key=language_key,
        year=year,
        evolution_history=world.language_evolution_history,
    )


def apply_language_evolution_record(world: Any, record: LanguageEvolutionRecord) -> bool:
    """Apply one language evolution record to the world runtime snapshot."""
    updated_runtime_states = apply_evolution_record(
        world.language_engine,
        world._language_runtime_states,
        record,
    )
    if updated_runtime_states is None:
        return False
    world._language_runtime_states = updated_runtime_states
    return True


def apply_language_evolution_from_event(
    world: Any,
    record: Any,
    *,
    language_key: str | None = None,
    cause_key: str = "",
) -> LanguageEvolutionRecord | None:
    """Apply one immediate language evolution record caused by a world event."""
    return apply_event_language_evolution(
        world,
        record,
        language_key=language_key,
        cause_key=cause_key,
    )


def maybe_evolve_languages_for_year(world: Any, year: int) -> None:
    """Advance language evolution for one simulation year."""
    advance_world_languages_for_year(world, year)
