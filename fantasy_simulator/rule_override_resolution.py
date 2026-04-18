"""Public owner for simulation rule defaults, validation, and override resolution."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from .world_topology import (
    PROPAGATION_TOPOLOGY_TRAVEL,
    VALID_PROPAGATION_TOPOLOGIES,
)

DISABLED_ROAD_DAMAGE_THRESHOLD = 101


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

DEFAULT_PROPAGATION_RULES: Dict[str, Dict[str, Any]] = {
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
    "topology": {
        "mode": PROPAGATION_TOPOLOGY_TRAVEL,
        "include_blocked_routes": False,
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


def _validate_probability(*, section: str, key: str, value: Any) -> None:
    if value < 0 or value > 1:
        raise ValueError(f"PROPAGATION_RULES[{section!r}][{key!r}] must be between 0 and 1")


def _validate_non_negative_int(*, section: str, key: str, value: Any) -> None:
    if value < 0:
        raise ValueError(f"PROPAGATION_RULES[{section!r}][{key!r}] must be >= 0")


def _validate_percentage_threshold(*, section: str, key: str, value: Any) -> None:
    if value < 0 or value > 100:
        raise ValueError(f"PROPAGATION_RULES[{section!r}][{key!r}] must be between 0 and 100")


def is_disabled_threshold(value: int) -> bool:
    """Return True when a threshold intentionally disables a propagation effect."""
    return value == DISABLED_ROAD_DAMAGE_THRESHOLD


def validate_propagation_rules(rules: Mapping[str, Mapping[str, Any]]) -> None:
    """Validate propagation rule schema (DbC fail-fast for configuration errors)."""
    required = {
        "danger": ("decay", "cap", "min_source"),
        "traffic": ("decay", "cap", "min_source"),
        "mood_from_ruin": ("source_threshold", "neighbor_penalty", "max_neighbors"),
        "road_damage_from_danger": ("danger_threshold", "road_penalty"),
        "topology": ("mode", "include_blocked_routes"),
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
    expected_bool = {
        "topology": ("include_blocked_routes",),
    }
    expected_string = {
        "topology": ("mode",),
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
        for key in expected_bool.get(section, ()):
            value = values[key]
            if not isinstance(value, bool):
                raise ValueError(f"PROPAGATION_RULES[{section!r}][{key!r}] must be bool, got {type(value)!r}")
        for key in expected_string.get(section, ()):
            value = values[key]
            if not isinstance(value, str):
                raise ValueError(f"PROPAGATION_RULES[{section!r}][{key!r}] must be str, got {type(value)!r}")

    _validate_probability(section="danger", key="decay", value=rules["danger"]["decay"])
    _validate_probability(section="traffic", key="decay", value=rules["traffic"]["decay"])
    _validate_non_negative_int(section="danger", key="cap", value=rules["danger"]["cap"])
    _validate_non_negative_int(section="danger", key="min_source", value=rules["danger"]["min_source"])
    _validate_non_negative_int(section="traffic", key="cap", value=rules["traffic"]["cap"])
    _validate_non_negative_int(section="traffic", key="min_source", value=rules["traffic"]["min_source"])
    _validate_percentage_threshold(
        section="mood_from_ruin",
        key="source_threshold",
        value=rules["mood_from_ruin"]["source_threshold"],
    )
    _validate_non_negative_int(
        section="mood_from_ruin",
        key="neighbor_penalty",
        value=rules["mood_from_ruin"]["neighbor_penalty"],
    )
    _validate_non_negative_int(
        section="mood_from_ruin",
        key="max_neighbors",
        value=rules["mood_from_ruin"]["max_neighbors"],
    )
    danger_threshold = rules["road_damage_from_danger"]["danger_threshold"]
    if danger_threshold < 0:
        raise ValueError("PROPAGATION_RULES['road_damage_from_danger']['danger_threshold'] must be >= 0")
    if danger_threshold > 100 and not is_disabled_threshold(danger_threshold):
        raise ValueError(
            "PROPAGATION_RULES['road_damage_from_danger']['danger_threshold'] "
            "must be between 0 and 100, or 101 to disable"
        )
    _validate_non_negative_int(
        section="road_damage_from_danger",
        key="road_penalty",
        value=rules["road_damage_from_danger"]["road_penalty"],
    )
    topology_mode = rules["topology"]["mode"]
    if topology_mode not in VALID_PROPAGATION_TOPOLOGIES:
        raise ValueError(
            "PROPAGATION_RULES['topology']['mode'] must be one of "
            f"{', '.join(VALID_PROPAGATION_TOPOLOGIES)}"
        )


def clone_default_event_impact_rules() -> Dict[str, Dict[str, int]]:
    """Return a mutable deep copy of bundled default impact rules."""
    return deepcopy(DEFAULT_EVENT_IMPACT_RULES)


def clone_default_propagation_rules() -> Dict[str, Dict[str, Any]]:
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
) -> Dict[str, Dict[str, Any]]:
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
