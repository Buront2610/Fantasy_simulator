"""Adventure lifecycle management for the Simulator.

Handles adventure creation, step-by-step progression, dead-character
resolution, and player-facing query methods.

PR-E: Extended with party adventure formation (design §9.1–§9.4).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..adventure import (
    AdventureRun,
    SUPPLY_FULL,
    create_adventure_run,
    default_retreat_rule_for_policy,
    generate_adventure_id,
    select_party_policy,
)
from ..narrative.context import alias_for_event, epitaph_for_character
from ..i18n import tr

if TYPE_CHECKING:
    from ..character import Character


# Maximum party size for auto-formed parties
_MAX_PARTY_SIZE = 3
# Probability that a new adventure attempt forms a party (vs solo)
_PARTY_FORMATION_CHANCE = 0.30


class AdventureMixin:
    """Mixin providing adventure management methods for the Simulator.

    Expected attributes on *self* (provided by ``engine.Simulator``):
    - ``world``: the World instance
    - ``current_month``: current in-world month (1–12)
    - ``adventure_steps_per_year``: steps to advance per year
    - ``event_system``: EventSystem instance
    - ``rng``, ``id_rng``: RNG instances
    - ``_recently_completed_adventures``: list of recently completed runs
    """

    def _maybe_start_adventure(self) -> None:
        """Start at most one new adventure (solo or party) in the current year."""
        candidates = [
            c for c in self.world.characters
            if c.alive and c.active_adventure_id is None
            and c.injury_status not in ("injured", "serious", "dying")
        ]
        if not candidates or self.rng.random() >= 0.25:
            return

        # 30% chance to form a party adventure when enough candidates exist
        if len(candidates) >= 2 and self.rng.random() < _PARTY_FORMATION_CHANCE:
            self._start_party_adventure(candidates)
        else:
            self._start_solo_adventure(candidates)

    def _start_solo_adventure(self, candidates: List["Character"]) -> None:
        """Pick one candidate and start a solo adventure."""
        char = self.rng.choice(candidates)
        run = create_adventure_run(char, self.world, rng=self.rng, id_rng=self.id_rng)
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
        """Form a small party from candidates and start a shared adventure.

        Party size: 2–_MAX_PARTY_SIZE members.
        Leader is the first selected character.
        Policy is AI-selected unless spotlighted/playable leader is present
        (player UI hook reserved for future enhancement).
        Design §9.3: policy selection by character status.
        """
        # Prefer locally co-located parties for world consistency.
        # Future extension hook: if co-located candidates are insufficient,
        # allow "gather for one month" travel-to-rally behavior instead of
        # instant cross-map assembly.
        leader = self.rng.choice(candidates)
        same_location = [c for c in candidates if c.location_id == leader.location_id and c.char_id != leader.char_id]
        other_locations = [c for c in candidates if c.location_id != leader.location_id and c.char_id != leader.char_id]

        size = self.rng.choice(range(2, _MAX_PARTY_SIZE + 1))
        size = min(size, len(candidates))
        needed_companions = max(0, size - 1)
        selected_companions = self.rng.sample(same_location, min(needed_companions, len(same_location)))
        if len(selected_companions) < needed_companions:
            remaining = needed_companions - len(selected_companions)
            selected_companions.extend(self.rng.sample(other_locations, min(remaining, len(other_locations))))
        members = [leader] + selected_companions
        leader = members[0]

        # Build adventure on leader
        run = create_adventure_run(leader, self.world, rng=self.rng, id_rng=self.id_rng)

        # Apply party data
        run.member_ids = [m.char_id for m in members]
        run.party_id = generate_adventure_id(self.id_rng)
        run.policy = select_party_policy(members, self.rng)
        run.retreat_rule = default_retreat_rule_for_policy(run.policy)
        run.supply_state = SUPPLY_FULL
        # danger_level already set in create_adventure_run from destination.danger

        # Override the initial summary with party text if multi-member
        if len(members) > 1:
            party_names = self._format_party_names(members)
            origin_name = self.world.location_name(run.origin)
            dest_name = self.world.location_name(run.destination)
            run.summary_log = [
                tr("summary_party_set_out", party=party_names,
                   origin=origin_name, destination=dest_name)
            ]
            run.detail_log = [
                tr("detail_party_set_out", party=party_names,
                   origin=origin_name, destination=dest_name)
            ]

        # Mark all members as on this adventure
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

    @staticmethod
    def _format_party_names(members: List["Character"], max_shown: int = 3) -> str:
        """Return a display string for party members  (e.g. 'Aldric & Lysara')."""
        names = [m.name for m in members[:max_shown]]
        result = " & ".join(names)
        if len(members) > max_shown:
            result += f" +{len(members) - max_shown}"
        return result

    def _advance_adventures(self) -> None:
        """Advance active adventures by multiple internal steps per year."""
        paused_until_next_year = set()
        for _ in range(self.adventure_steps_per_year):
            active_ids = [run.adventure_id for run in self.world.active_adventures]
            for adventure_id in active_ids:
                if adventure_id in paused_until_next_year:
                    continue
                run = self.world.get_adventure_by_id(adventure_id)
                if run is None or run.is_resolved:
                    continue
                char = self.world.get_character_by_id(run.character_id)
                if char is None:
                    continue
                if not char.alive:
                    self._resolve_dead_character_adventure(run, char)
                    continue
                had_pending_choice = run.pending_choice is not None
                previous_state = run.state
                summaries = run.step(char, self.world, rng=self.rng)
                for entry in summaries:
                    kind, location_id, severity = self._classify_adventure_summary(previous_state, run)
                    self._record_world_event(
                        entry,
                        kind=kind,
                        location_id=location_id,
                        primary_actor_id=run.character_id,
                        severity=severity,
                    )
                if not char.alive:
                    self.event_system.handle_death_side_effects(char, self.world)
                if run.is_resolved:
                    if run.outcome == "death":
                        deceased = self.world.get_character_by_id(run.death_member_id or run.character_id)
                        if deceased is not None and not deceased.alive:
                            self.event_system.handle_death_side_effects(deceased, self.world)
                    self._apply_world_memory(run)
                    self._recently_completed_adventures.append(run)
                    self.world.complete_adventure(run.adventure_id)
                elif not had_pending_choice and run.pending_choice is not None:
                    paused_until_next_year.add(run.adventure_id)

    def _resolve_dead_character_adventure(self, run: AdventureRun, char: "Character") -> None:
        run.pending_choice = None
        run.state = "resolved"
        run.outcome = "death"
        run.resolution_year = self.world.year
        char.active_adventure_id = None
        # Clear all other party members
        for mid in run.member_ids:
            if mid != run.character_id:
                member = self.world.get_character_by_id(mid)
                if member is not None:
                    member.active_adventure_id = None
        char.add_history(
            tr(
                "history_adventure_detail",
                year=self.world.year,
                detail=tr(
                    "detail_adventure_died", name=char.name,
                    destination=self.world.location_name(run.destination),
                ),
            )
        )
        self.event_system.handle_death_side_effects(char, self.world)
        self._apply_world_memory(run)
        self._recently_completed_adventures.append(run)
        self.world.complete_adventure(run.adventure_id)

    def _apply_world_memory(self, run: AdventureRun) -> None:
        """Record live traces, memorials, and aliases from a resolved adventure.

        PR-F (design §E-2): Called for every resolved adventure to leave
        footprints at the destination.  Deaths additionally create a
        permanent memorial and may generate a location alias.

        Does NOT consume RNG — all IDs are generated via ``self.id_rng``.
        """
        dest = run.destination
        dest_name = self.world.location_name(dest)

        # -- Live trace (all outcomes) -----------------------------------
        if run.is_party:
            members = [self.world.get_character_by_id(mid) for mid in run.member_ids]
            names = [m.name for m in members if m is not None]
            if not names:
                names = [run.character_name]
            party_str = self._format_party_names_from_list(names)
            if run.outcome == "retreat":
                trace_key = "live_trace_party_retreat"
            elif run.outcome == "injury":
                trace_key = "live_trace_party_injury"
            else:
                trace_key = "live_trace_party_safe"
            trace_text = tr(trace_key, party=party_str, destination=dest_name, year=self.world.year)
        else:
            if run.outcome == "retreat":
                trace_key = "live_trace_solo_retreat"
            elif run.outcome == "injury":
                trace_key = "live_trace_solo_injury"
            else:
                trace_key = "live_trace_solo_safe"
            trace_text = tr(trace_key, name=run.character_name, destination=dest_name, year=self.world.year)
        self.world.add_live_trace(dest, self.world.year, run.character_name, trace_text)

        # -- Memorial + alias (death only) --------------------------------
        if run.outcome == "death":
            deceased_id = run.death_member_id or run.character_id
            char = self.world.get_character_by_id(deceased_id)
            char_name = char.name if char is not None else run.character_name
            epitaph = epitaph_for_character(
                char_name,
                self.world.year,
                dest_name,
                "adventure_death",
                char=char,
            )
            memorial_id = generate_adventure_id(self.id_rng)
            self.world.add_memorial(
                memorial_id,
                deceased_id,
                char_name,
                dest,
                self.world.year,
                "adventure_death",
                epitaph,
            )
            # Generate a location alias (capped by World.MAX_ALIASES)
            dest_loc = self.world.get_location_by_id(dest)
            if dest_loc is not None:
                alias = alias_for_event("adventure_death", char_name, dest_name)
                self.world.add_alias(dest, alias)

    def get_adventure_summaries(self, include_active: bool = True) -> List[str]:
        """Return summary lines for known adventures."""
        runs = list(self.world.completed_adventures)
        if include_active:
            runs.extend(self.world.active_adventures)
        summaries: List[str] = []
        for run in runs:
            status_key = f"outcome_{run.outcome}" if run.outcome else f"state_{run.state}"
            status = tr(status_key)
            origin_name = self.world.location_name(run.origin)
            dest_name = self.world.location_name(run.destination)
            # Show all party members for party adventures
            if run.is_party:
                party_names = self._build_party_display_names(run)
                summaries.append(
                    f"{party_names}: {origin_name} -> {dest_name} [{status}]"
                )
            else:
                summaries.append(
                    f"{run.character_name}: {origin_name} -> {dest_name} [{status}]"
                )
        return summaries

    def _build_party_display_names(self, run: AdventureRun) -> str:
        """Return display names for party members, falling back to leader name."""
        names = []
        for mid in run.member_ids:
            c = self.world.get_character_by_id(mid)
            if c is not None:
                names.append(c.name)
        if not names:
            names = [run.character_name]
        return self._format_party_names_from_list(names)

    @staticmethod
    def _format_party_names_from_list(names: List[str], max_shown: int = 3) -> str:
        shown = names[:max_shown]
        result = " & ".join(shown)
        if len(names) > max_shown:
            result += f" +{len(names) - max_shown}"
        return result

    def get_adventure_details(self, adventure_id: str) -> List[str]:
        """Return detailed log entries for a specific adventure."""
        run = self.world.get_adventure_by_id(adventure_id)
        if run is None:
            return []
        return list(run.detail_log)

    def get_pending_adventure_choices(self) -> List[Dict[str, Any]]:
        """Return all unresolved adventure choices."""
        pending: List[Dict[str, Any]] = []
        for run in self.world.active_adventures:
            if run.pending_choice is not None:
                pending.append(
                    {
                        "adventure_id": run.adventure_id,
                        "character_id": run.character_id,
                        "character_name": run.character_name,
                        "prompt": run.pending_choice.prompt,
                        "options": list(run.pending_choice.options),
                        "default_option": run.pending_choice.default_option,
                    }
                )
        return pending

    def resolve_adventure_choice(
        self,
        adventure_id: str,
        option: Optional[str] = None,
    ) -> bool:
        """Resolve a pending choice on a specific adventure."""
        run = self.world.get_adventure_by_id(adventure_id)
        if run is None or run.pending_choice is None:
            return False
        char = self.world.get_character_by_id(run.character_id)
        if char is None:
            return False
        summaries = run.resolve_choice(self.world, char, option=option)
        for entry in summaries:
            self._record_world_event(
                entry,
                kind="adventure_choice",
                month=self.current_month,
                location_id=run.destination,
                primary_actor_id=run.character_id,
            )
        return True
