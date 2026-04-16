"""Public owner for simulation rule defaults, validation, and override resolution."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping


_VALID_IMPACT_ATTRIBUTES = {
    "prosperity",
    "safety",
    "mood",
    "danger",
    "traffic",
    "rumor_heat",
    "road_condition",
}

DEFAULT_EVENT_IMPACT_RULES: Dict[str, Dict[str, int]] = {
    "death": {"safety": -3, "mood": -5, "rumor_heat": +10},
    "battle_fatal": {"safety": -5, "mood": -8, "danger": +5, "rumor_heat": +15},
    "battle": {"safety": -2, "mood": -3, "danger": +3, "rumor_heat": +5},
    "discovery": {"rumor_heat": +5, "traffic": +3},
    "marriage": {"mood": +3},
    "adventure_death": {"danger": +5, "mood": -5, "rumor_heat": +10},
    "adventure_discovery": {"rumor_heat": +5, "traffic": +2, "prosperity": +2},
    "adventure_started": {"traffic": +2},
    "adventure_returned": {"mood": +2, "traffic": +1},
    "journey": {"traffic": +1},
    "injury_recovery": {"mood": +1},
    "condition_worsened": {"mood": -2, "rumor_heat": +3},
    "dying_rescued": {"mood": +3, "rumor_heat": +5},
}

DEFAULT_PROPAGATION_RULES: Dict[str, Dict[str, float | int]] = {
    "danger": {
        "decay": 0.30,
        "cap": 15,
        "min_source": 40,
    },
    "traffic": {
        "decay": 0.20,
        "cap": 10,
        "min_source": 35,
    },
    "mood_from_ruin": {
        "source_threshold": 20,
        "neighbor_penalty": 5,
        "max_neighbors": 4,
    },
    "road_damage_from_danger": {
        "danger_threshold": 70,
        "road_penalty": 8,
    },
}


def validate_event_impact_rules(rules: Mapping[str, Mapping[str, int]]) -> None:
    """Validate impact-rule schema (DbC fail-fast for configuration errors)."""
    for kind, deltas in rules.items():
        for attr, delta in deltas.items():
            if attr not in _VALID_IMPACT_ATTRIBUTES:
                raise ValueError(f"Unsupported impact attribute in EVENT_IMPACT_RULES[{kind!r}]: {attr}")
            if not isinstance(delta, int) or isinstance(delta, bool):
                raise ValueError(
                    f"Unsupported impact delta type in EVENT_IMPACT_RULES[{kind!r}][{attr!r}]: {type(delta)!r}"
                )


def validate_propagation_rules(rules: Mapping[str, Mapping[str, float | int]]) -> None:
    """Validate propagation rule schema (DbC fail-fast for configuration errors)."""
    required = {
        "danger": ("decay", "cap", "min_source"),
        "traffic": ("decay", "cap", "min_source"),
        "mood_from_ruin": ("source_threshold", "neighbor_penalty", "max_neighbors"),
        "road_damage_from_danger": ("danger_threshold", "road_penalty"),
    }
    expected_int = {
        "danger": ("cap", "min_source"),
        "traffic": ("cap", "min_source"),
        "mood_from_ruin": ("source_threshold", "neighbor_penalty", "max_neighbors"),
        "road_damage_from_danger": ("danger_threshold", "road_penalty"),
    }
    expected_numeric = {
        "danger": ("decay",),
        "traffic": ("decay",),
    }

    for section, keys in required.items():
        if section not in rules:
            raise ValueError(f"PROPAGATION_RULES missing section: {section}")
        values = rules[section]
        for key in keys:
            if key not in values:
                raise ValueError(f"PROPAGATION_RULES[{section!r}] missing key: {key}")
        for key in expected_int.get(section, ()):
            value = values[key]
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"PROPAGATION_RULES[{section!r}][{key!r}] must be int, got {type(value)!r}")
        for key in expected_numeric.get(section, ()):
            value = values[key]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"PROPAGATION_RULES[{section!r}][{key!r}] must be numeric, got {type(value)!r}")


def clone_default_event_impact_rules() -> Dict[str, Dict[str, int]]:
    """Return a mutable deep copy of bundled default impact rules."""
    return deepcopy(DEFAULT_EVENT_IMPACT_RULES)


def clone_default_propagation_rules() -> Dict[str, Dict[str, float | int]]:
    """Return a mutable deep copy of bundled default propagation rules."""
    return deepcopy(DEFAULT_PROPAGATION_RULES)


def resolve_event_impact_rule_overrides(
    overrides: Mapping[str, Mapping[str, Any]] | None,
) -> Dict[str, Dict[str, int]]:
    """Layer event impact overrides onto the canonical default table."""
    merged = clone_default_event_impact_rules()
    if overrides:
        for kind, deltas in overrides.items():
            if not isinstance(deltas, Mapping):
                raise ValueError(f"event_impact_rules[{kind!r}] must be an object")
            bucket = merged.setdefault(str(kind), {})
            for attr, delta in deltas.items():
                bucket[str(attr)] = delta
    validate_event_impact_rules(merged)
    return {
        kind: {attr: int(delta) for attr, delta in deltas.items()}
        for kind, deltas in merged.items()
    }


def resolve_propagation_rule_overrides(
    overrides: Mapping[str, Mapping[str, Any]] | None,
) -> Dict[str, Dict[str, float | int]]:
    """Layer propagation overrides onto the canonical default table."""
    merged = clone_default_propagation_rules()
    if overrides:
        for section, values in overrides.items():
            if section not in merged:
                raise ValueError(f"Unsupported propagation section: {section}")
            if not isinstance(values, Mapping):
                raise ValueError(f"propagation_rules[{section!r}] must be an object")
            for key, value in values.items():
                if key not in merged[section]:
                    raise ValueError(f"Unsupported propagation key in propagation_rules[{section!r}]: {key}")
                merged[section][str(key)] = value
    validate_propagation_rules(merged)
    return {
        section: dict(values)
        for section, values in merged.items()
    }


validate_event_impact_rules(DEFAULT_EVENT_IMPACT_RULES)
validate_propagation_rules(DEFAULT_PROPAGATION_RULES)
