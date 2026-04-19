"""Language-specific helpers for ``World``.

Keeps language engine orchestration and endonym/evolution helpers out of the
core world aggregate so ``world.py`` can stay focused on world state wiring.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Sequence

from .content.setting_bundle import WorldDefinition
from .language.engine import LanguageEngine
from .language.state import LanguageEvolutionRecord, LanguageRuntimeState


def language_signature(world_definition: WorldDefinition) -> List[Dict[str, Any]]:
    """Return a stable signature for bundle language definitions."""
    return [language.to_dict() for language in world_definition.languages]


def prune_runtime_states(
    world_definition: WorldDefinition,
    runtime_states: Dict[str, LanguageRuntimeState],
) -> Dict[str, LanguageRuntimeState]:
    """Drop runtime states for language keys no longer present in the bundle."""
    valid_language_keys = {language.language_key for language in world_definition.languages}
    return {
        key: state
        for key, state in runtime_states.items()
        if key in valid_language_keys
    }


def build_language_engine(
    world_definition: WorldDefinition,
    runtime_states: Dict[str, LanguageRuntimeState],
) -> LanguageEngine:
    """Create a language engine for the active world definition."""
    return LanguageEngine(world_definition, runtime_states=runtime_states)


def resolve_language_display_name(
    language_engine: LanguageEngine,
    *,
    race: str | None = None,
    tribe: str | None = None,
    region: str | None = None,
) -> str | None:
    """Resolve a display-facing language name for an identity selector."""
    language = language_engine.resolve_language(race=race, tribe=tribe, region=region)
    if language is None:
        return None
    return language.display_name


def location_endonym(
    world_definition: WorldDefinition,
    language_engine: LanguageEngine,
    location_id: str,
) -> str | None:
    """Resolve a site-native name or generated endonym for a location."""
    for seed in world_definition.site_seeds:
        if seed.location_id != location_id:
            continue
        if seed.native_name:
            return seed.native_name
        language_key = seed.language_key
        if not language_key:
            language = language_engine.resolve_language(region=location_id)
            language_key = language.language_key if language is not None else ""
        if not language_key:
            return None
        return language_engine.generate_toponym(
            language_key,
            seed_key=location_id,
            region_type=seed.region_type,
        )
    return None


def language_status(
    world_definition: WorldDefinition,
    language_engine: LanguageEngine,
    evolution_history: Sequence[LanguageEvolutionRecord],
) -> List[Dict[str, Any]]:
    """Build UI-facing language status summaries."""
    statuses: List[Dict[str, Any]] = []
    for language in world_definition.languages:
        profile = language_engine.profile(language.language_key)
        evolution_count = sum(
            1 for record in evolution_history if record.language_key == language.language_key
        )
        statuses.append(
            {
                "language_key": language.language_key,
                "display_name": language.display_name,
                "lineage": list(profile.lineage),
                "sample_given_names": profile.naming_rules.first_names_male[:3],
                "sample_surnames": profile.naming_rules.last_names[:3],
                "sound_shifts": language_engine.effective_sound_shift_map(language.language_key),
                "evolution_interval_years": int(language.evolution_interval_years),
                "evolution_count": evolution_count,
            }
        )
    return statuses


def evolution_records_for_language(
    evolution_history: Sequence[LanguageEvolutionRecord],
    language_key: str,
) -> List[LanguageEvolutionRecord]:
    """Filter evolution records to a single language."""
    return [
        record
        for record in evolution_history
        if record.language_key == language_key
    ]


def refresh_generated_endonym_aliases(
    *,
    locations: Iterable[Any],
    max_aliases: int,
    endonym_resolver: Callable[[str], str | None],
) -> None:
    """Ensure generated endonyms are present as aliases on live locations."""
    for location in locations:
        endonym = endonym_resolver(location.id)
        if endonym and endonym != location.canonical_name and endonym not in location.aliases:
            if len(location.aliases) < max_aliases:
                location.aliases.append(endonym)


def derive_evolution_record(
    language_engine: LanguageEngine,
    *,
    language_key: str,
    year: int,
    evolution_history: Sequence[LanguageEvolutionRecord],
) -> LanguageEvolutionRecord | None:
    """Ask the language engine for the next historical change event."""
    return language_engine.derive_evolution_record(
        language_key,
        year=year,
        evolution_history=evolution_history,
    )


def apply_evolution_record(
    language_engine: LanguageEngine,
    runtime_states: Dict[str, LanguageRuntimeState],
    record: LanguageEvolutionRecord,
) -> Dict[str, LanguageRuntimeState] | None:
    """Apply a change record and return an updated runtime-state snapshot."""
    changed = language_engine.apply_evolution_record(record)
    if not changed:
        return None
    return language_engine.runtime_states_snapshot()


def maybe_evolve_languages_for_year(
    *,
    world_definition: WorldDefinition,
    language_engine: LanguageEngine,
    language_origin_year: int,
    evolution_history: List[LanguageEvolutionRecord],
    runtime_states: Dict[str, LanguageRuntimeState],
    year: int,
) -> tuple[List[LanguageEvolutionRecord], Dict[str, LanguageRuntimeState], bool]:
    """Advance language history for a simulation year if intervals match."""
    changed = False
    next_history = list(evolution_history)
    next_runtime_states = dict(runtime_states)
    for language in world_definition.languages:
        interval = int(language.evolution_interval_years)
        if interval <= 0 or year <= language_origin_year:
            continue
        if (year - language_origin_year) % interval != 0:
            continue
        already_applied = any(
            record.year == year and record.language_key == language.language_key
            for record in next_history
        )
        if already_applied:
            continue
        record = derive_evolution_record(
            language_engine,
            language_key=language.language_key,
            year=year,
            evolution_history=next_history,
        )
        if record is None:
            continue
        updated_runtime_states = apply_evolution_record(language_engine, next_runtime_states, record)
        if updated_runtime_states is None:
            continue
        next_runtime_states = updated_runtime_states
        next_history.append(record)
        changed = True
    return next_history, next_runtime_states, changed
