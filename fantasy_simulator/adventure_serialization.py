"""AdventureRun serialization helpers."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Type, TypeVar, cast

from .adventure_constants import POLICY_CAUTIOUS, RETREAT_ON_SERIOUS, SUPPLY_FULL
from .adventure_protocols import AdventureRunLike
from .adventure_validation import validate_adventure_run_payload


TAdventureRun = TypeVar("TAdventureRun")


class AdventureSerialization:
    @staticmethod
    def to_dict(run: AdventureRunLike) -> Dict[str, Any]:
        return {
            "character_id": run.character_id,
            "character_name": run.character_name,
            "origin": run.origin,
            "destination": run.destination,
            "year_started": run.year_started,
            "adventure_id": run.adventure_id,
            "state": run.state,
            "injury_status": run.injury_status,
            "steps_taken": run.steps_taken,
            "pending_choice": run.pending_choice.to_dict() if run.pending_choice is not None else None,
            "outcome": run.outcome,
            "loot_summary": list(run.loot_summary),
            "summary_log": list(run.summary_log),
            "detail_log": list(run.detail_log),
            "resolution_year": run.resolution_year,
            "injury_member_id": run.injury_member_id,
            "death_member_id": run.death_member_id,
            "member_ids": list(run.member_ids),
            "party_id": run.party_id,
            "policy": run.policy,
            "retreat_rule": run.retreat_rule,
            "supply_state": run.supply_state,
            "danger_level": run.danger_level,
        }

    @staticmethod
    def from_dict(run_cls: Type[TAdventureRun], choice_cls: Type[Any], data: Dict[str, Any]) -> TAdventureRun:
        pending = data.get("pending_choice")
        character_id = data["character_id"]
        member_ids = data.get("member_ids") or [character_id]
        if not isinstance(member_ids, list) or any(not isinstance(member_id, str) for member_id in member_ids):
            raise ValueError("member_ids must be a list of strings")
        run_factory = cast(Any, run_cls)
        run = run_factory(
            character_id=character_id,
            character_name=data["character_name"],
            origin=data["origin"],
            destination=data["destination"],
            year_started=data["year_started"],
            adventure_id=data.get("adventure_id", uuid.uuid4().hex[:10]),
            state=data.get("state", "traveling"),
            injury_status=data.get("injury_status", "none"),
            steps_taken=data.get("steps_taken", 0),
            pending_choice=choice_cls.from_dict(pending) if pending else None,
            outcome=data.get("outcome"),
            loot_summary=list(data.get("loot_summary", [])),
            summary_log=list(data.get("summary_log", [])),
            detail_log=list(data.get("detail_log", [])),
            resolution_year=data.get("resolution_year"),
            injury_member_id=data.get("injury_member_id"),
            death_member_id=data.get("death_member_id"),
            member_ids=list(member_ids),
            party_id=data.get("party_id"),
            policy=data.get("policy", POLICY_CAUTIOUS),
            retreat_rule=data.get("retreat_rule", RETREAT_ON_SERIOUS),
            supply_state=data.get("supply_state", SUPPLY_FULL),
            danger_level=data.get("danger_level", 50),
        )
        validate_adventure_run_payload(run)
        return run
