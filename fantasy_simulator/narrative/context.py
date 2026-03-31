"""
narrative/context.py - Minimal NarrativeContext for world memory generation.

PR-F: Provides just enough context-aware text selection for memorial
epitaphs and location aliases.  Full NarrativeContext expansion
(relation tags, reports, world memory integration) is deferred to PR-H.

Design §E-2: "NarrativeContext 導入前でも最低限のテンプレート選択で
memorial / alias テキストを安定生成する"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Sequence

from ..i18n import tr
from ..reports import generate_yearly_report
from .constants import (
    EVENT_KIND_ADVENTURE_DEATH,
    EVENT_KIND_BATTLE_FATAL,
    EVENT_KIND_DEATH,
)
from .template_history import TemplateHistory

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World


_CLOSE_RELATION_TAGS = ("spouse", "family", "friend", "savior", "rescued")
# Prefer the most intimate / narratively defining tie first, leaving "rival"
# as a fallback so close-loss tones win over adversarial tones when both exist.
_RELATION_PRIORITY = ("spouse", "family", "savior", "rescued", "friend", "rival")


@dataclass(frozen=True)
class NarrativeContext:
    """Narrative selection context derived from relations, reports, and memory."""

    relation_tags: Sequence[str] = field(default_factory=tuple)
    yearly_death_count: int = 0
    report_notable_count: int = 0
    location_memorial_count: int = 0
    location_alias_count: int = 0
    location_trace_count: int = 0

    @property
    def primary_relation_tag(self) -> Optional[str]:
        for tag in _RELATION_PRIORITY:
            if tag in self.relation_tags:
                return tag
        return self.relation_tags[0] if self.relation_tags else None

    @property
    def has_close_relation(self) -> bool:
        return any(tag in _CLOSE_RELATION_TAGS for tag in self.relation_tags)

    @property
    def is_tragic_site(self) -> bool:
        return (
            self.yearly_death_count >= 2
            or self.report_notable_count >= 2
            or self.location_memorial_count >= 1
        )


def build_narrative_context(
    world: "World",
    location_id: str,
    year: int,
    *,
    observer: Optional["Character"] = None,
    subject_id: Optional[str] = None,
) -> NarrativeContext:
    """Build a minimal PR-I context from relation tags, reports, and world memory."""
    relation_tags: Sequence[str] = ()
    if observer is not None and subject_id:
        relation_tags = tuple(observer.get_relation_tags(subject_id))

    yearly_report = generate_yearly_report(world, year)
    location_report = next(
        (entry for entry in yearly_report.location_entries if entry.location_id == location_id),
        None,
    )
    location = world.get_location_by_id(location_id)
    memorials = world.get_memorials_for_location(location_id)
    aliases = list(location.aliases) if location is not None else []
    traces = list(location.live_traces) if location is not None else []
    notable_count = len(location_report.notable_events) if location_report is not None else 0
    return NarrativeContext(
        relation_tags=relation_tags,
        yearly_death_count=yearly_report.deaths_this_year,
        report_notable_count=notable_count,
        location_memorial_count=len(memorials),
        location_alias_count=len(aliases),
        location_trace_count=len(traces),
    )


# ---------------------------------------------------------------------------
# Job category classification for epitaph variant selection
# ---------------------------------------------------------------------------

# Combat-oriented jobs → warrior epitaph
_COMBAT_JOBS: frozenset = frozenset({
    "Warrior", "Knight", "Paladin", "Ranger", "Mercenary",
})

# Magic / knowledge-oriented jobs → mage epitaph
_MAGIC_JOBS: frozenset = frozenset({
    "Mage", "Witch", "Healer", "Sage", "Druid", "Bard",
})


def epitaph_for_character(
    char_name: str,
    year: int,
    location_name: str,
    cause: str,
    char: Optional["Character"] = None,
    template_history: Optional[TemplateHistory] = None,
    relation_hint: Optional[str] = None,
    title_hint: Optional[str] = None,
    favorite: bool = False,
    context: Optional[NarrativeContext] = None,
) -> str:
    """Return a context-aware memorial epitaph string.

    Selects from warrior / mage / adventurer / default variants based on
    the character's job.  When *char* is None (e.g. during legacy data
    migration), falls back to the adventurer or default template.

    Args:
        char_name: Display name of the deceased.
        year: The year the death occurred.
        location_name: Human-readable name of the death location.
        cause: Event kind, e.g. ``"adventure_death"``, ``"battle_fatal"``.
        char: Live ``Character`` object for job-based variant selection.
    """
    candidates: List[str] = []
    active_relation = relation_hint or getattr(context, "primary_relation_tag", None)
    if active_relation == "rival":
        candidates.append("memorial_epitaph_rival")
    elif active_relation in _CLOSE_RELATION_TAGS or favorite or title_hint:
        candidates.append("memorial_epitaph_beloved")
    elif context is not None and context.is_tragic_site:
        candidates.append("memorial_epitaph_tragic_year")

    if char is not None:
        job = getattr(char, "job", "")
        if job in _COMBAT_JOBS:
            candidates.append("memorial_epitaph_warrior")
        elif job in _MAGIC_JOBS:
            candidates.append("memorial_epitaph_mage")

    if cause in (EVENT_KIND_ADVENTURE_DEATH, "death_cause_dungeon"):
        candidates.extend(["memorial_epitaph_adventurer", "memorial_epitaph_default"])
    else:
        candidates.extend(["memorial_epitaph_default", "memorial_epitaph_adventurer"])

    if template_history is not None:
        return tr(template_history.choose(candidates), name=char_name, year=year, location=location_name)
    return tr(candidates[0], name=char_name, year=year, location=location_name)


def alias_for_event(
    event_kind: str,
    char_name: str,
    location_name: str,
    template_history: Optional[TemplateHistory] = None,
    relation_hint: Optional[str] = None,
    context: Optional[NarrativeContext] = None,
) -> str:
    """Return a location alias string generated from a significant event.

    Args:
        event_kind: The event kind that triggered alias generation,
            e.g. ``"adventure_death"``, ``"battle_fatal"``.
        char_name: The primary character associated with the event.
        location_name: The canonical location name (for context only;
            the alias text is standalone).
    """
    candidates: List[str] = []
    if event_kind in (EVENT_KIND_ADVENTURE_DEATH, EVENT_KIND_DEATH, EVENT_KIND_BATTLE_FATAL):
        if context is not None and context.location_memorial_count >= 1:
            candidates.append("alias_memorial_site")
        if context is not None and context.location_trace_count >= 3:
            candidates.append("alias_fallen_path")
        candidates.append("alias_death_site")
    else:
        candidates.append("alias_notable_site")
    if template_history is not None:
        key = template_history.choose(candidates)
        return tr(key, name=char_name)
    key = candidates[0]
    return tr(key, name=char_name)
