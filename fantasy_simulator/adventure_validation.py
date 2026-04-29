"""Validation helpers for adventure run payloads."""

from __future__ import annotations

from .adventure_constants import (
    ALL_POLICIES,
    ALL_RETREAT_RULES,
    SUPPLY_CRITICAL,
    SUPPLY_FULL,
    SUPPLY_LOW,
)
from .adventure_protocols import AdventureRunLike


def validate_adventure_run_payload(run: AdventureRunLike) -> None:
    if run.policy not in ALL_POLICIES:
        raise ValueError(f"policy must be one of {ALL_POLICIES}")
    if run.retreat_rule not in ALL_RETREAT_RULES:
        raise ValueError(f"retreat_rule must be one of {ALL_RETREAT_RULES}")
    if run.supply_state not in (SUPPLY_FULL, SUPPLY_LOW, SUPPLY_CRITICAL):
        raise ValueError("supply_state must be one of ('full', 'low', 'critical')")
    if not isinstance(run.danger_level, int) or isinstance(run.danger_level, bool):
        raise ValueError("danger_level must be an integer")
    if run.danger_level < 0 or run.danger_level > 100:
        raise ValueError("danger_level must be between 0 and 100")
    if not isinstance(run.member_ids, list) or any(not isinstance(member_id, str) for member_id in run.member_ids):
        raise ValueError("member_ids must be a list of strings")
    if run.member_ids and run.character_id not in run.member_ids:
        raise ValueError("member_ids must include character_id")
