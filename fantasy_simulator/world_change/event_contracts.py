"""Event-record contracts for PR-K world-change records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from fantasy_simulator.event_models import WorldEventRecord


@dataclass(frozen=True)
class WorldChangeEventContract:
    """Machine-checkable contract for a world-change event kind."""

    kind: str
    required_render_params: frozenset[str]
    required_tags: frozenset[str]
    required_impact_attributes: frozenset[str]
    requires_impact: bool = True


WORLD_CHANGE_EVENT_CONTRACTS: Mapping[str, WorldChangeEventContract] = {
    "route_blocked": WorldChangeEventContract(
        kind="route_blocked",
        required_render_params=frozenset({"route_id", "from_location_id", "to_location_id"}),
        required_tags=frozenset({"world_change"}),
        required_impact_attributes=frozenset({"blocked"}),
    ),
    "route_reopened": WorldChangeEventContract(
        kind="route_reopened",
        required_render_params=frozenset({"route_id", "from_location_id", "to_location_id"}),
        required_tags=frozenset({"world_change"}),
        required_impact_attributes=frozenset({"blocked"}),
    ),
    "location_renamed": WorldChangeEventContract(
        kind="location_renamed",
        required_render_params=frozenset({"location_id", "old_name", "new_name"}),
        required_tags=frozenset({"world_change"}),
        required_impact_attributes=frozenset({"canonical_name"}),
    ),
    "location_faction_changed": WorldChangeEventContract(
        kind="location_faction_changed",
        required_render_params=frozenset({"location_id", "old_faction_id", "new_faction_id"}),
        required_tags=frozenset({"world_change"}),
        required_impact_attributes=frozenset({"controlling_faction_id"}),
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
    ),
    "era_shifted": WorldChangeEventContract(
        kind="era_shifted",
        required_render_params=frozenset(
            {"old_era_key", "new_era_key", "old_civilization_phase", "new_civilization_phase"}
        ),
        required_tags=frozenset({"world_change", "era"}),
        required_impact_attributes=frozenset({"era_key", "civilization_phase"}),
    ),
    "civilization_phase_drifted": WorldChangeEventContract(
        kind="civilization_phase_drifted",
        required_render_params=frozenset(
            {"era_key", "old_civilization_phase", "new_civilization_phase", "score_changes"}
        ),
        required_tags=frozenset({"world_change", "era", "civilization"}),
        required_impact_attributes=frozenset({"civilization_phase"}),
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
    impact_attributes = {
        impact.get("attribute")
        for impact in record.impacts
        if isinstance(impact, dict)
    }
    if contract.requires_impact and not impact_attributes:
        raise ValueError(f"{record.kind} must include at least one impact")
    missing_impacts = contract.required_impact_attributes - impact_attributes
    if missing_impacts:
        raise ValueError(f"{record.kind} missing impact attributes: {sorted(missing_impacts)}")
