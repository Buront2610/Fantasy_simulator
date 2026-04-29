"""Resolved-adventure world-memory helpers for the simulator."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from ..adventure import AdventureRun, generate_adventure_id
from ..i18n import tr
from ..narrative.context import alias_for_event, build_narrative_context, derive_relation_hint, epitaph_for_character

if TYPE_CHECKING:
    from ..character import Character


class AdventureMemoryMixin:
    """Mixin for recording traces, memorials, and aliases from adventures."""

    def _apply_world_memory(self, run: AdventureRun) -> None:
        """Record live traces, memorials, and aliases from a resolved adventure."""
        dest = run.destination
        dest_name = self.world.location_name(dest)

        trace_text = self._build_adventure_trace_text(run, dest_name)
        self.world.add_live_trace(dest, self.world.year, run.character_name, trace_text)

        if run.outcome != "death":
            return
        self._record_adventure_death_memory(run, dest, dest_name)

    def _build_adventure_trace_text(self, run: AdventureRun, dest_name: str) -> str:
        """Return localized live-trace text for a resolved adventure."""
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
            return tr(trace_key, party=party_str, destination=dest_name, year=self.world.year)

        if run.outcome == "retreat":
            trace_key = "live_trace_solo_retreat"
        elif run.outcome == "injury":
            trace_key = "live_trace_solo_injury"
        else:
            trace_key = "live_trace_solo_safe"
        return tr(trace_key, name=run.character_name, destination=dest_name, year=self.world.year)

    def _record_adventure_death_memory(self, run: AdventureRun, dest: str, dest_name: str) -> None:
        """Create memorial and alias records for an adventure death."""
        memorial_template_history = getattr(self, "memorial_template_history", None)
        alias_template_history = getattr(self, "alias_template_history", None)
        deceased_id = run.death_member_id or run.character_id
        char = self.world.get_character_by_id(deceased_id)
        char_name = char.name if char is not None else run.character_name
        observers = self._surviving_observers_for_deceased(run, deceased_id)
        context = build_narrative_context(
            self.world,
            dest,
            self.world.year,
            observer=observers,
            subject_id=deceased_id,
        )
        relation_hint = derive_relation_hint(observers, deceased_id)
        epitaph = epitaph_for_character(
            char_name,
            self.world.year,
            dest_name,
            "adventure_death",
            char=char,
            template_history=memorial_template_history,
            relation_hint=relation_hint,
            context=context,
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
        dest_loc = self.world.get_location_by_id(dest)
        if dest_loc is None:
            return
        alias = alias_for_event(
            "adventure_death",
            char_name,
            dest_name,
            template_history=alias_template_history,
            relation_hint=relation_hint,
            context=context,
        )
        self.world.add_alias(dest, alias)

    def _surviving_observers_for_deceased(
        self,
        run: AdventureRun,
        deceased_id: str,
    ) -> List["Character"]:
        """Return living party observers for directional relation lookup."""
        if not getattr(run, "is_party", False):
            return []
        observers: List["Character"] = []
        for member_id in getattr(run, "member_ids", []):
            if member_id == deceased_id:
                continue
            observer = self.world.get_character_by_id(member_id)
            if observer is not None and observer.alive:
                observers.append(observer)
        return observers
