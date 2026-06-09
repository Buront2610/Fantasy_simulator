"""Event-record contracts for PR-K world-change records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from fantasy_simulator.event_models import LOCATION_TAG_PREFIX, WorldEventRecord

from .state_machines import WORLD_SCORE_KEYS


IMPACT_SHAPE_KEYS = frozenset({"target_type", "target_id", "attribute", "old_value", "new_value"})
TERRAIN_MUTATION_ATTRIBUTES = frozenset({"biome", "elevation", "moisture", "temperature"})


@dataclass(frozen=True)
class WorldChangeEventContract:
    """Machine-checkable contract for a world-change event kind."""

    kind: str
    required_render_params: frozenset[str]
    required_tags: frozenset[str]
    required_impact_attributes: frozenset[str]
    allowed_impact_attributes: frozenset[str]
    location_tag_render_params: frozenset[str] = frozenset()
    requires_impact: bool = True


WORLD_CHANGE_EVENT_CONTRACTS: Mapping[str, WorldChangeEventContract] = {
    "war_declared": WorldChangeEventContract(
        kind="war_declared",
        required_render_params=frozenset(
            {"aggressor_faction_id", "target_faction_id", "belligerent_faction_ids", "location_ids"}
        ),
        required_tags=frozenset({"world_change", "war"}),
        required_impact_attributes=frozenset(),
        allowed_impact_attributes=frozenset(),
        requires_impact=False,
    ),
    "war_ended": WorldChangeEventContract(
        kind="war_ended",
        required_render_params=frozenset(
            {"aggressor_faction_id", "target_faction_id", "belligerent_faction_ids", "location_ids"}
        ),
        required_tags=frozenset({"world_change", "war"}),
        required_impact_attributes=frozenset(),
        allowed_impact_attributes=frozenset(),
        requires_impact=False,
    ),
    "route_blocked": WorldChangeEventContract(
        kind="route_blocked",
        required_render_params=frozenset({"route_id", "from_location_id", "to_location_id"}),
        required_tags=frozenset({"world_change"}),
        required_impact_attributes=frozenset({"blocked"}),
        allowed_impact_attributes=frozenset({"blocked"}),
        location_tag_render_params=frozenset({"from_location_id", "to_location_id"}),
    ),
    "route_reopened": WorldChangeEventContract(
        kind="route_reopened",
        required_render_params=frozenset({"route_id", "from_location_id", "to_location_id"}),
        required_tags=frozenset({"world_change"}),
        required_impact_attributes=frozenset({"blocked"}),
        allowed_impact_attributes=frozenset({"blocked"}),
        location_tag_render_params=frozenset({"from_location_id", "to_location_id"}),
    ),
    "location_renamed": WorldChangeEventContract(
        kind="location_renamed",
        required_render_params=frozenset({"location_id", "old_name", "new_name"}),
        required_tags=frozenset({"world_change"}),
        required_impact_attributes=frozenset({"canonical_name"}),
        allowed_impact_attributes=frozenset({"canonical_name"}),
        location_tag_render_params=frozenset({"location_id"}),
    ),
    "location_faction_changed": WorldChangeEventContract(
        kind="location_faction_changed",
        required_render_params=frozenset({"location_id", "old_faction_id", "new_faction_id"}),
        required_tags=frozenset({"world_change"}),
        required_impact_attributes=frozenset({"controlling_faction_id"}),
        allowed_impact_attributes=frozenset({"controlling_faction_id"}),
        location_tag_render_params=frozenset({"location_id"}),
    ),
    "terrain_cell_mutated": WorldChangeEventContract(
        kind="terrain_cell_mutated",
        required_render_params=frozenset(
            {
                "terrain_cell_id",
                "x",
                "y",
                "old_biome",
                "new_biome",
            }
        ),
        required_tags=frozenset({"world_change", "terrain"}),
        required_impact_attributes=frozenset(),
        allowed_impact_attributes=TERRAIN_MUTATION_ATTRIBUTES,
        location_tag_render_params=frozenset({"location_id"}),
    ),
    "era_shifted": WorldChangeEventContract(
        kind="era_shifted",
        required_render_params=frozenset(
            {"old_era_key", "new_era_key", "old_civilization_phase", "new_civilization_phase"}
        ),
        required_tags=frozenset({"world_change", "era"}),
        required_impact_attributes=frozenset({"era_key", "civilization_phase"}),
        allowed_impact_attributes=frozenset({"era_key", "civilization_phase"}),
    ),
    "civilization_phase_drifted": WorldChangeEventContract(
        kind="civilization_phase_drifted",
        required_render_params=frozenset(
            {"era_key", "old_civilization_phase", "new_civilization_phase", "score_changes"}
        ),
        required_tags=frozenset({"world_change", "era", "civilization"}),
        required_impact_attributes=frozenset({"civilization_phase"}),
        allowed_impact_attributes=frozenset({"civilization_phase", *WORLD_SCORE_KEYS}),
    ),
}


def validate_world_change_event_contract(record: WorldEventRecord) -> None:
    """Raise when a world-change event record violates its registered contract."""
    contract = WORLD_CHANGE_EVENT_CONTRACTS.get(record.kind)
    if contract is None:
        raise ValueError(f"unknown world-change event contract: {record.kind}")
    missing_params = contract.required_render_params - set(record.render_params)
    if missing_params:
        raise ValueError(f"{record.kind} missing render_params: {sorted(missing_params)}")
    missing_tags = contract.required_tags - set(record.tags)
    if missing_tags:
        raise ValueError(f"{record.kind} missing tags: {sorted(missing_tags)}")
    _validate_location_tags(record, contract)
    impacts = _validate_impact_shape(record)
    impact_attributes = {impact["attribute"] for impact in impacts}
    if contract.requires_impact and not impact_attributes:
        raise ValueError(f"{record.kind} must include at least one impact")
    unknown_impacts = impact_attributes - contract.allowed_impact_attributes
    if record.kind == "civilization_phase_drifted":
        unknown_impacts -= _world_score_attributes_from_record(record)
    if unknown_impacts:
        raise ValueError(f"{record.kind} has unknown impact attributes: {sorted(unknown_impacts)}")
    missing_impacts = contract.required_impact_attributes - impact_attributes
    if missing_impacts:
        raise ValueError(f"{record.kind} missing impact attributes: {sorted(missing_impacts)}")
    if record.kind == "terrain_cell_mutated":
        _validate_terrain_changed_attributes(record, impacts)


def _world_score_attributes_from_record(record: WorldEventRecord) -> set[str]:
    score_changes = record.render_params.get("score_changes", [])
    if not isinstance(score_changes, list):
        return set()
    attributes: set[str] = set()
    for change in score_changes:
        if isinstance(change, dict) and isinstance(change.get("score_key"), str):
            attributes.add(change["score_key"])
    return attributes


def _validate_location_tags(record: WorldEventRecord, contract: WorldChangeEventContract) -> None:
    for param_name in contract.location_tag_render_params:
        if param_name not in record.render_params:
            continue
        expected_tag = f"{LOCATION_TAG_PREFIX}{record.render_params[param_name]}"
        if expected_tag not in record.tags:
            raise ValueError(f"{record.kind} missing location tag: {expected_tag}")


def _validate_impact_shape(record: WorldEventRecord) -> list[dict[str, Any]]:
    impacts: list[dict[str, Any]] = []
    for index, impact in enumerate(record.impacts):
        if not isinstance(impact, dict):
            raise ValueError(f"{record.kind} impact #{index} must be a JSON object")
        missing_keys = IMPACT_SHAPE_KEYS - set(impact)
        if missing_keys:
            raise ValueError(f"{record.kind} impact #{index} missing keys: {sorted(missing_keys)}")
        for key in ("target_type", "target_id", "attribute"):
            if not isinstance(impact[key], str) or not impact[key].strip():
                raise ValueError(f"{record.kind} impact #{index} has invalid {key}")
        impacts.append(impact)
    return impacts


def _validate_terrain_changed_attributes(record: WorldEventRecord, impacts: list[dict[str, Any]]) -> None:
    changed_attributes = record.render_params.get("changed_attributes")
    if not isinstance(changed_attributes, list) or not changed_attributes:
        raise ValueError("terrain_cell_mutated must include non-empty changed_attributes")
    if any(not isinstance(attribute, str) for attribute in changed_attributes):
        raise ValueError("terrain_cell_mutated changed_attributes must be strings")
    changed_attribute_set = set(changed_attributes)
    if len(changed_attribute_set) != len(changed_attributes):
        raise ValueError("terrain_cell_mutated changed_attributes contains duplicates")
    unknown_changed = changed_attribute_set - TERRAIN_MUTATION_ATTRIBUTES
    if unknown_changed:
        raise ValueError(
            f"terrain_cell_mutated changed_attributes contains unknown attributes: {sorted(unknown_changed)}"
        )

    impact_attributes = {impact["attribute"] for impact in impacts}
    if changed_attribute_set != impact_attributes:
        raise ValueError("terrain_cell_mutated changed_attributes disagree with impact attributes")
    for impact in impacts:
        attribute = impact["attribute"]
        old_key = f"old_{attribute}"
        new_key = f"new_{attribute}"
        if old_key not in record.render_params or new_key not in record.render_params:
            raise ValueError(f"terrain_cell_mutated missing render params for {attribute!r}")
        if impact["old_value"] != record.render_params[old_key] or impact["new_value"] != record.render_params[new_key]:
            raise ValueError(f"terrain_cell_mutated impact values disagree with render params for {attribute!r}")
