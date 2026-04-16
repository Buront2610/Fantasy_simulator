from __future__ import annotations

import pytest

from fantasy_simulator.rule_override_resolution import (
    clone_default_event_impact_rules,
    clone_default_propagation_rules,
    resolve_event_impact_rule_overrides,
    resolve_propagation_rule_overrides,
    validate_event_impact_rules,
    validate_propagation_rules,
)


def test_event_impact_rule_resolution_layers_partial_overrides_onto_defaults() -> None:
    resolved = resolve_event_impact_rule_overrides({"meeting": {"mood": 7}})

    assert resolved["meeting"]["mood"] == 7
    assert resolved["battle"]["danger"] == 3


def test_propagation_rule_resolution_layers_partial_overrides_onto_defaults() -> None:
    resolved = resolve_propagation_rule_overrides(
        {"road_damage_from_danger": {"danger_threshold": 101, "road_penalty": 0}}
    )

    assert resolved["road_damage_from_danger"]["danger_threshold"] == 101
    assert resolved["danger"]["cap"] == 15


def test_clone_default_rule_tables_are_defensive_copies() -> None:
    impact_rules = clone_default_event_impact_rules()
    propagation_rules = clone_default_propagation_rules()

    impact_rules["battle"]["danger"] = 99
    propagation_rules["danger"]["cap"] = 99

    fresh_impact_rules = clone_default_event_impact_rules()
    fresh_propagation_rules = clone_default_propagation_rules()
    assert fresh_impact_rules["battle"]["danger"] == 3
    assert fresh_propagation_rules["danger"]["cap"] == 15


def test_validate_event_impact_rules_rejects_unknown_attribute() -> None:
    rules = clone_default_event_impact_rules()
    rules["meeting"] = {"curiosity": 3}

    with pytest.raises(ValueError, match="Unsupported impact attribute"):
        validate_event_impact_rules(rules)


def test_validate_propagation_rules_rejects_missing_required_key() -> None:
    rules = clone_default_propagation_rules()
    del rules["danger"]["cap"]

    with pytest.raises(ValueError, match="missing key: cap"):
        validate_propagation_rules(rules)
