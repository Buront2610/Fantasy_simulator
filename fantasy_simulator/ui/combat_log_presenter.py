"""Player-facing combat log formatting helpers."""

from __future__ import annotations

from typing import Any, List

from ..i18n import tr, tr_term


def combat_log_lines_for_event(record: Any) -> List[str]:
    """Return readable combat rounds stored on a world event record."""
    combat_log = _combat_log_from_record(record)
    if not combat_log:
        return []
    return [tr("combat_log_header"), *[_render_combat_round(entry) for entry in combat_log]]


def combat_log_lines_for_adventure(run: Any, world: Any) -> List[str]:
    """Return readable combat encounters stored on an adventure run."""
    lines: List[str] = []
    for entry in getattr(run, "combat_logs", []):
        if not isinstance(entry, dict):
            continue
        combat_log = entry.get("combat_log")
        if not isinstance(combat_log, list) or not combat_log:
            continue
        lines.append(_render_adventure_encounter(entry, world))
        lines.extend(_render_combat_round(round_entry) for round_entry in combat_log if isinstance(round_entry, dict))
    return lines


def _combat_log_from_record(record: Any) -> List[dict[str, Any]]:
    render_params = getattr(record, "render_params", {})
    if isinstance(render_params, dict):
        combat_log = _dict_list(render_params.get("combat_log"))
        if combat_log:
            return combat_log

    legacy_event_result = getattr(record, "legacy_event_result", None)
    if isinstance(legacy_event_result, dict):
        metadata = legacy_event_result.get("metadata", {})
        if isinstance(metadata, dict):
            return _dict_list(metadata.get("combat_log"))
    return []


def _dict_list(value: Any) -> List[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _render_adventure_encounter(entry: dict[str, Any], world: Any) -> str:
    location = _location_name(world, str(entry.get("location_id", "")))
    return tr(
        "combat_log_adventure_encounter",
        member=_display_value(entry.get("member_name")),
        hazard=_display_value(entry.get("hazard_name")),
        location=location,
        step=_display_value(entry.get("step")),
    )


def _render_combat_round(entry: dict[str, Any]) -> str:
    skill = _display_skill(entry.get("skill_key"))
    return tr(
        "combat_log_round",
        round=_display_value(entry.get("round_number")),
        actor=_display_value(entry.get("actor_name")),
        action=_display_action(entry.get("action_kind")),
        skill=skill,
        target=_display_value(entry.get("target_name")),
        dice=_display_value(entry.get("dice")),
        modifier=_display_modifier(entry.get("modifier")),
        attack_total=_display_value(entry.get("attack_total")),
        defense_total=_display_value(entry.get("defense_total")),
        damage=_display_value(entry.get("damage")),
        outcome=_display_outcome(entry.get("outcome")),
    )


def _display_action(value: Any) -> str:
    key = f"combat_action_{value}" if isinstance(value, str) and value else "combat_action_weapon_attack"
    rendered = tr(key)
    return rendered if rendered != key else str(value)


def _display_outcome(value: Any) -> str:
    key = f"combat_outcome_{value}" if isinstance(value, str) and value else "combat_outcome_unknown"
    rendered = tr(key)
    return rendered if rendered != key else str(value)


def _display_skill(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return tr("combat_skill_basic")
    return tr_term(value)


def _display_modifier(value: Any) -> str:
    modifier = _int_or_none(value)
    if modifier is None:
        return "+0"
    return f"{modifier:+d}"


def _display_value(value: Any) -> str:
    if value is None or value == "":
        return tr("combat_log_unknown")
    return str(value)


def _location_name(world: Any, location_id: str) -> str:
    if not location_id:
        return tr("combat_log_unknown")
    location_name = getattr(world, "location_name", None)
    if callable(location_name):
        try:
            return str(location_name(location_id))
        except (KeyError, TypeError, ValueError):
            pass
    return location_id


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
