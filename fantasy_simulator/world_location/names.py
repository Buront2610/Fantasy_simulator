"""Location naming read models for endonym and etymology previews."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, TYPE_CHECKING

from ..i18n import tr

if TYPE_CHECKING:
    from ..content.setting_bundle import LanguageDefinition, SiteSeedDefinition
    from ..world import World


@dataclass(frozen=True)
class ToponymComponent:
    """A display-facing piece of a location-name explanation."""

    role: str
    surface: str
    gloss: str = ""


@dataclass(frozen=True)
class ToponymEtymology:
    """Read model for a location's current naming evidence."""

    location_id: str
    canonical_name: str
    language_key: str = ""
    language_name: str = ""
    source: str = ""
    surface_name: str = ""
    pattern: str = ""
    components: List[ToponymComponent] = field(default_factory=list)


def build_toponym_etymology(world: "World", location_id: str) -> ToponymEtymology | None:
    """Build a non-persistent etymology preview for a location, if language data exists."""
    location = world.get_location_by_id(location_id)
    if location is None:
        raise ValueError(f"Unknown location id: {location_id}")

    world_definition = world.setting_bundle.world_definition
    seed = world_definition.site_seed_by_id(location_id)
    if seed is None:
        return None

    language = _resolve_site_language(world, seed)
    if language is None:
        return None

    rename_etymology = _latest_language_rename_etymology(world, location, seed)
    if rename_etymology is not None:
        return rename_etymology

    native_name = seed.native_name.strip()
    if native_name:
        return ToponymEtymology(
            location_id=location_id,
            canonical_name=location.canonical_name,
            language_key=language.language_key,
            language_name=language.display_name,
            source="authored_native_name",
            surface_name=native_name,
            components=[
                ToponymComponent("native", native_name, "authored local form"),
                ToponymComponent("canonical", location.canonical_name, "common map name"),
            ],
        )

    generated = location.generated_endonym or world.location_endonym(location_id) or ""
    if not generated:
        return None

    trace = world.language_engine.trace_toponym(
        language.language_key,
        seed_key=location_id,
        region_type=seed.region_type,
    )
    return ToponymEtymology(
        location_id=location_id,
        canonical_name=location.canonical_name,
        language_key=language.language_key,
        language_name=language.display_name,
        source="generated_endonym",
        surface_name=generated,
        pattern=trace.pattern,
        components=_components_from_trace(trace.primary_stem, trace.secondary_stem, trace.suffix, seed),
    )


def _latest_language_rename_etymology(
    world: "World",
    location: object,
    seed: "SiteSeedDefinition",
) -> ToponymEtymology | None:
    current_name = str(getattr(location, "canonical_name", "")).strip()
    location_id = str(getattr(location, "id", "")).strip()
    for record in reversed(getattr(world, "event_records", [])):
        if record.kind != "location_renamed" or record.location_id != location_id:
            continue
        params = record.render_params
        if params.get("new_name") != current_name:
            continue
        if params.get("name_source") != "language_generated_rename":
            return None
        language_key = str(params.get("name_language_key", "")).strip()
        seed_key = str(params.get("name_language_seed_key", "")).strip()
        region_type = str(params.get("name_language_region_type", "")).strip()
        language = _language_by_key(world, language_key)
        if language is None or not seed_key:
            return None
        trace = world.language_engine.trace_toponym(
            language.language_key,
            seed_key=seed_key,
            region_type=region_type,
        )
        return ToponymEtymology(
            location_id=location_id,
            canonical_name=current_name,
            language_key=language.language_key,
            language_name=language.display_name,
            source="language_generated_rename",
            surface_name=current_name,
            pattern=trace.pattern,
            components=_components_from_trace(trace.primary_stem, trace.secondary_stem, trace.suffix, seed),
        )
    return None


def render_toponym_etymology_line(etymology: ToponymEtymology) -> str:
    """Render a compact single-line explanation for location detail surfaces."""
    prefix = tr(
        "location_etymology_prefix",
        surface_name=etymology.surface_name,
        language_name=etymology.language_name,
    )
    if etymology.source == "authored_native_name":
        return tr(
            "location_etymology_authored",
            prefix=prefix,
            canonical_name=etymology.canonical_name,
        )
    parts = [
        tr(
            "location_etymology_component",
            role=component.role,
            surface=component.surface,
        )
        for component in etymology.components
        if component.surface
    ]
    pattern = (
        tr("location_etymology_pattern", pattern=etymology.pattern)
        if etymology.pattern
        else ""
    )
    component_text = (
        tr("location_etymology_components", components=", ".join(parts))
        if parts
        else ""
    )
    return tr(
        "location_etymology_generated",
        prefix=prefix,
        pattern=pattern,
        components=component_text,
    )


def _resolve_site_language(world: "World", seed: "SiteSeedDefinition") -> "LanguageDefinition | None":
    if seed.language_key:
        language = _language_by_key(world, seed.language_key)
        if language is not None:
            return language
    return world.language_engine.resolve_language(region=seed.location_id)


def _language_by_key(world: "World", language_key: str) -> "LanguageDefinition | None":
    for language in world.setting_bundle.world_definition.languages:
        if language.language_key == language_key:
            return language
    return None


def _components_from_trace(
    primary_stem: str,
    secondary_stem: str,
    suffix: str,
    seed: "SiteSeedDefinition",
) -> List[ToponymComponent]:
    components = [
        ToponymComponent("stem", primary_stem, "toponym stem"),
    ]
    if secondary_stem and secondary_stem != primary_stem:
        components.append(ToponymComponent("secondary_stem", secondary_stem, "short-form stem"))
    if suffix:
        components.append(ToponymComponent("suffix", suffix, "toponym suffix"))
    components.append(ToponymComponent("region", seed.region_type, "site region type"))
    return components
