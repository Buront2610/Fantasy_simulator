"""Facts emitted at the decision point, before canonical event IDs are assigned."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .protocols import AdventureRunLike
from ..i18n import tr

AdventureFactKind = Literal[
    "adventure_arrived", "adventure_scouted", "adventure_discovery", "adventure_encounter",
    "adventure_injured", "adventure_death", "adventure_returned", "adventure_returned_injured",
    "adventure_retreated", "adventure_retreat_started", "adventure_choice",
    "adventure_travel", "adventure_route_blocked",
]


@dataclass(frozen=True)
class AdventureStepFact:
    kind: AdventureFactKind
    location_id: str
    primary_actor_id: str
    secondary_actor_ids: tuple[str, ...]
    cause_event_ids: tuple[str, ...]
    severity: int
    summary_key: str
    render_params: dict[str, Any]

    @property
    def description(self) -> str:
        return tr(self.summary_key, **self.render_params)


@dataclass(frozen=True)
class AdventureStepResult:
    """An applied domain step; atomic world recording is a separate boundary."""

    adventure_id: str
    new_state: str
    facts: tuple[AdventureStepFact, ...] = ()
    summaries: tuple[str, ...] = ()


def step_fact_result(
    run: AdventureRunLike,
    kind: AdventureFactKind,
    summary_key: str,
    params: dict[str, Any],
    *,
    actor_id: str | None = None,
    location_id: str | None = None,
    severity: int = 1,
    show_summary: bool = True,
) -> AdventureStepResult:
    """Capture explicit subject, companions and causality without inspecting logs."""
    subject = actor_id or run.character_id
    members = tuple(dict.fromkeys([run.character_id, *run.member_ids]))
    if subject not in members:
        raise ValueError("Adventure fact subject must be a party member")
    event_summary_key = "events." + summary_key.removeprefix("summary_").removeprefix("detail_") + ".summary"
    fact = AdventureStepFact(
        kind=kind, location_id=location_id or run.destination, primary_actor_id=subject,
        secondary_actor_ids=tuple(member for member in members if member != subject),
        cause_event_ids=tuple(run.related_event_ids[-1:]), severity=severity, summary_key=event_summary_key,
        render_params={
            **params, "adventure_id": run.adventure_id, "step": run.steps_taken,
            "participant_roles": {
                member: "leader" if member == run.character_id else "companion" for member in members
            },
        },
    )
    return AdventureStepResult(run.adventure_id, run.state, (fact,), (fact.description,) if show_summary else ())
