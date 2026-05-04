"""Small state machines for PR-K world-change slices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping


RouteStatus = Literal["open", "blocked"]
CivilizationPhase = Literal["stable", "crisis", "transition", "new_era", "aftermath"]

CIVILIZATION_PHASES: tuple[CivilizationPhase, ...] = (
    "stable",
    "crisis",
    "transition",
    "new_era",
    "aftermath",
)
WORLD_SCORE_KEYS = ("prosperity", "safety", "traffic", "mood")


@dataclass(frozen=True)
class RouteStateTransition:
    """A route blocked/open transition."""

    old_blocked: bool
    new_blocked: bool
    old_status: RouteStatus
    new_status: RouteStatus
    event_kind: Literal["route_blocked", "route_reopened"]


@dataclass(frozen=True)
class LocationNameTransition:
    """An official location name transition."""

    old_name: str
    new_name: str
    old_aliases: tuple[str, ...]
    new_aliases: tuple[str, ...]
    alias_added: bool
    event_kind: Literal["location_renamed"] = "location_renamed"


@dataclass(frozen=True)
class LocationOccupationTransition:
    """A location controlling-faction/occupation transition."""

    old_faction_id: str | None
    new_faction_id: str | None
    event_kind: Literal["location_faction_changed"] = "location_faction_changed"


@dataclass(frozen=True)
class EraShiftTransition:
    """A world era transition."""

    old_era_key: str
    new_era_key: str
    old_civilization_phase: CivilizationPhase
    new_civilization_phase: CivilizationPhase
    event_kind: Literal["era_shifted"] = "era_shifted"


@dataclass(frozen=True)
class CivilizationPhaseTransition:
    """A civilization phase transition within the current era."""

    old_phase: CivilizationPhase
    new_phase: CivilizationPhase
    event_kind: Literal["civilization_phase_drifted"] = "civilization_phase_drifted"


@dataclass(frozen=True)
class WorldScoreTransition:
    """A bounded world-score transition caused by civilization drift."""

    score_key: str
    old_value: int
    new_value: int

    @property
    def delta(self) -> int:
        return self.new_value - self.old_value


@dataclass(frozen=True)
class TerrainCellTransition:
    """A runtime terrain-cell transition."""

    x: int
    y: int
    old_biome: str
    new_biome: str
    old_elevation: int
    new_elevation: int
    old_moisture: int
    new_moisture: int
    old_temperature: int
    new_temperature: int
    event_kind: Literal["terrain_cell_mutated"] = "terrain_cell_mutated"

    @property
    def changed_attributes(self) -> tuple[str, ...]:
        attributes: list[str] = []
        if self.old_biome != self.new_biome:
            attributes.append("biome")
        if self.old_elevation != self.new_elevation:
            attributes.append("elevation")
        if self.old_moisture != self.new_moisture:
            attributes.append("moisture")
        if self.old_temperature != self.new_temperature:
            attributes.append("temperature")
        return tuple(attributes)


def route_status(blocked: bool) -> RouteStatus:
    """Return the semantic route status for the current PR-K route slice."""
    if not isinstance(blocked, bool):
        raise TypeError("blocked must be a bool")
    return "blocked" if blocked else "open"


def transition_route_blocked_state(old_blocked: bool, requested_blocked: bool) -> RouteStateTransition | None:
    """Return the route transition, or ``None`` when the request is a no-op."""
    if not isinstance(old_blocked, bool) or not isinstance(requested_blocked, bool):
        raise TypeError("blocked must be a bool")
    if old_blocked == requested_blocked:
        return None
    return RouteStateTransition(
        old_blocked=old_blocked,
        new_blocked=requested_blocked,
        old_status=route_status(old_blocked),
        new_status=route_status(requested_blocked),
        event_kind="route_blocked" if requested_blocked else "route_reopened",
    )


def transition_location_name(
    *,
    old_name: str,
    requested_name: str,
    aliases: list[str],
    max_aliases: int,
) -> LocationNameTransition | None:
    """Return a location-name transition, or ``None`` when the request is a no-op."""
    normalized_name = requested_name.strip()
    if not normalized_name:
        raise ValueError("new_name must not be blank")
    if old_name == normalized_name:
        return None
    old_aliases = tuple(aliases)
    new_aliases = list(aliases)
    alias_added = bool(old_name) and old_name not in new_aliases and len(new_aliases) < max_aliases
    if alias_added:
        new_aliases.append(old_name)
    return LocationNameTransition(
        old_name=old_name,
        new_name=normalized_name,
        old_aliases=old_aliases,
        new_aliases=tuple(new_aliases),
        alias_added=alias_added,
    )


def transition_location_occupation_state(
    old_faction_id: str | None,
    requested_faction_id: str | None,
) -> LocationOccupationTransition | None:
    """Return an occupation/control transition, or ``None`` when the request is a no-op."""
    normalized_old = old_faction_id.strip() if isinstance(old_faction_id, str) and old_faction_id.strip() else None
    normalized_new = (
        requested_faction_id.strip()
        if isinstance(requested_faction_id, str) and requested_faction_id.strip()
        else None
    )
    if normalized_old == normalized_new:
        return None
    return LocationOccupationTransition(
        old_faction_id=normalized_old,
        new_faction_id=normalized_new,
    )


def transition_terrain_cell(
    *,
    x: int,
    y: int,
    old_biome: str,
    requested_biome: str,
    old_elevation: int,
    requested_elevation: int,
    old_moisture: int,
    requested_moisture: int,
    old_temperature: int,
    requested_temperature: int,
) -> TerrainCellTransition | None:
    """Return a terrain-cell transition, or ``None`` for an idempotent request."""
    transition = TerrainCellTransition(
        x=x,
        y=y,
        old_biome=old_biome,
        new_biome=requested_biome,
        old_elevation=old_elevation,
        new_elevation=requested_elevation,
        old_moisture=old_moisture,
        new_moisture=requested_moisture,
        old_temperature=old_temperature,
        new_temperature=requested_temperature,
    )
    if not transition.changed_attributes:
        return None
    return transition


def validate_civilization_phase(value: str) -> CivilizationPhase:
    """Return a normalized civilization phase or raise for unknown phase names."""
    normalized = value.strip()
    if normalized not in CIVILIZATION_PHASES:
        raise ValueError(f"unknown civilization phase: {value}")
    return normalized


def _normalize_era_key(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    return normalized


def transition_era_shift(
    *,
    old_era_key: str,
    requested_era_key: str,
    old_civilization_phase: str,
    requested_civilization_phase: str,
) -> EraShiftTransition | None:
    """Return an era transition, or ``None`` when the era key is unchanged."""
    normalized_old_era = _normalize_era_key(old_era_key, field_name="old_era_key")
    normalized_new_era = _normalize_era_key(requested_era_key, field_name="new_era_key")
    old_phase = validate_civilization_phase(old_civilization_phase)
    new_phase = validate_civilization_phase(requested_civilization_phase)
    if normalized_old_era == normalized_new_era:
        return None
    return EraShiftTransition(
        old_era_key=normalized_old_era,
        new_era_key=normalized_new_era,
        old_civilization_phase=old_phase,
        new_civilization_phase=new_phase,
    )


def transition_civilization_phase(
    old_phase: str,
    requested_phase: str,
) -> CivilizationPhaseTransition | None:
    """Return a civilization phase transition, or ``None`` for an idempotent phase request."""
    normalized_old = validate_civilization_phase(old_phase)
    normalized_new = validate_civilization_phase(requested_phase)
    if normalized_old == normalized_new:
        return None
    return CivilizationPhaseTransition(old_phase=normalized_old, new_phase=normalized_new)


def _score_value(value: int, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer")
    return max(0, min(100, value))


def transition_world_scores(
    current_scores: Mapping[str, int],
    score_deltas: Mapping[str, int],
) -> tuple[WorldScoreTransition, ...]:
    """Return bounded world-score transitions for non-zero score deltas."""
    transitions: list[WorldScoreTransition] = []
    for score_key, delta in score_deltas.items():
        if score_key not in WORLD_SCORE_KEYS:
            raise ValueError(f"unknown world score: {score_key}")
        if score_key not in current_scores:
            raise KeyError(score_key)
        if not isinstance(delta, int) or isinstance(delta, bool):
            raise TypeError(f"score delta for {score_key} must be an integer")
        old_value = _score_value(current_scores[score_key], field_name=f"world_scores.{score_key}")
        new_value = _score_value(old_value + delta, field_name=f"world_scores.{score_key}")
        if old_value != new_value:
            transitions.append(
                WorldScoreTransition(
                    score_key=score_key,
                    old_value=old_value,
                    new_value=new_value,
                )
            )
    return tuple(transitions)
