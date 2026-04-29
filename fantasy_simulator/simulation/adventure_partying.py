"""Adventure start and party-formation helpers for the simulator."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from ..adventure import (
    SUPPLY_FULL,
    create_adventure_run,
    default_retreat_rule_for_policy,
    generate_adventure_id,
)
from ..i18n import tr

if TYPE_CHECKING:
    from ..character import Character


# Maximum party size for auto-formed parties
_MAX_PARTY_SIZE = 3
# Probability that a new adventure attempt forms a party (vs solo)
_PARTY_FORMATION_CHANCE = 0.30


class AdventureStartMixin:
    """Mixin for creating solo and party adventures."""

    def _maybe_start_adventure(self, year_fraction: float = 1.0) -> None:
        """Start at most one new adventure during the current simulation step."""
        candidates = [
            c for c in self.world.characters
            if c.alive and c.active_adventure_id is None
            and c.injury_status not in ("injured", "serious", "dying")
        ]
        if not candidates:
            return
        start_chance = 0.25 if year_fraction >= 1.0 else 1.0 - ((1.0 - 0.25) ** year_fraction)
        if self.rng.random() >= start_chance:
            return

        if len(candidates) >= 2 and self.rng.random() < _PARTY_FORMATION_CHANCE:
            self._start_party_adventure(candidates)
        else:
            self._start_solo_adventure(candidates)

    def _start_solo_adventure(self, candidates: List["Character"]) -> None:
        """Pick one candidate and start a solo adventure."""
        char = self.rng.choice(candidates)
        try:
            run = create_adventure_run(char, self.world, rng=self.rng, id_rng=self.id_rng)
        except ValueError:
            return
        char.active_adventure_id = run.adventure_id
        char.add_history(
            tr(
                "set_out_for_adventure",
                year=self.world.year,
                origin=self.world.location_name(run.origin),
                destination=self.world.location_name(run.destination),
            )
        )
        self.world.add_adventure(run)
        self._record_world_event(
            run.summary_log[-1],
            kind="adventure_started",
            location_id=run.origin,
            primary_actor_id=char.char_id,
            severity=2,
        )

    def _start_party_adventure(self, candidates: List["Character"]) -> None:
        """Form a small party from candidates and start a shared adventure."""
        leader = self.rng.choice(candidates)
        same_location = [c for c in candidates if c.location_id == leader.location_id and c.char_id != leader.char_id]
        size = self.rng.choice(range(2, _MAX_PARTY_SIZE + 1))
        size = min(size, len(candidates))
        needed_companions = max(0, size - 1)
        selected_companions = self.rng.sample(same_location, min(needed_companions, len(same_location)))
        members = [leader] + selected_companions
        leader = members[0]

        try:
            run = create_adventure_run(leader, self.world, rng=self.rng, id_rng=self.id_rng)
        except ValueError:
            return

        run.party_id = generate_adventure_id(self.id_rng)
        selected_policy = self._select_party_policy(members)
        run.set_party_configuration(
            member_ids=[m.char_id for m in members],
            policy=selected_policy,
            retreat_rule=default_retreat_rule_for_policy(selected_policy),
        )
        run.supply_state = SUPPLY_FULL

        if len(members) > 1:
            party_names = self._format_party_names(members)
            origin_name = self.world.location_name(run.origin)
            dest_name = self.world.location_name(run.destination)
            run.summary_log = [
                tr("summary_party_set_out", party=party_names, origin=origin_name, destination=dest_name)
            ]
            run.detail_log = [
                tr("detail_party_set_out", party=party_names, origin=origin_name, destination=dest_name)
            ]

        for member in members:
            member.active_adventure_id = run.adventure_id
            member.add_history(
                tr(
                    "set_out_for_adventure",
                    year=self.world.year,
                    origin=self.world.location_name(run.origin),
                    destination=self.world.location_name(run.destination),
                )
            )

        self.world.add_adventure(run)
        self._record_world_event(
            run.summary_log[-1],
            kind="adventure_started",
            location_id=run.origin,
            primary_actor_id=leader.char_id,
            severity=2,
        )

    def _select_party_policy(self, members: List["Character"]) -> str:
        """Select a party policy through the coordinator compatibility symbol."""
        from . import adventure_coordinator

        return adventure_coordinator.select_party_policy(members, self.rng)

    @staticmethod
    def _format_party_names(members: List["Character"], max_shown: int = 3) -> str:
        """Return a display string for party members  (e.g. 'Aldric & Lysara')."""
        return AdventureStartMixin._format_party_names_from_list([m.name for m in members], max_shown=max_shown)

    @staticmethod
    def _format_party_names_from_list(names: List[str], max_shown: int = 3) -> str:
        shown = names[:max_shown]
        result = " & ".join(shown)
        if len(names) > max_shown:
            result += f" +{len(names) - max_shown}"
        return result
