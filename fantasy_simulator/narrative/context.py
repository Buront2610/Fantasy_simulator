"""
narrative/context.py - Minimal NarrativeContext for world memory generation.

PR-F established the minimal template-selection hooks for memorial
epitaphs and location aliases. PR-I extends those hooks with relation
tags, yearly reports, and world-memory signals while keeping the API
small and deterministic.

Design §E-2: "NarrativeContext 導入前でも最低限のテンプレート選択で
memorial / alias テキストを安定生成する"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Iterable, List, Optional, Sequence

from ..i18n import tr
from ..reports import generate_yearly_report
from .constants import (
    EVENT_KIND_ADVENTURE_DEATH,
    EVENT_KINDS_FATAL,
)
from .template_history import TemplateHistory

if TYPE_CHECKING:
    from ..character import Character
    from ..reports import YearlyReport
    from ..world import World


_CLOSE_RELATION_TAGS = ("spouse", "family", "friend", "savior", "rescued", "mentor", "disciple")
_ADVERSARIAL_RELATION_TAGS = ("betrayer", "rival")
# Prefer the most intimate / narratively defining tie first, leaving "rival"
# as a fallback so close-loss tones win over adversarial tones when both exist.
_RELATION_PRIORITY = ("spouse", "family", "savior", "rescued", "friend", "mentor", "disciple", "betrayer", "rival")
_GENERIC_CLOSE_EPITAPH_CANDIDATES = ("memorial_epitaph_companions", "memorial_epitaph_beloved")
_EPITAPH_RELATION_CANDIDATES = {
    "spouse": ("memorial_epitaph_spouse", *_GENERIC_CLOSE_EPITAPH_CANDIDATES),
    "family": ("memorial_epitaph_family", *_GENERIC_CLOSE_EPITAPH_CANDIDATES),
    "savior": ("memorial_epitaph_savior", *_GENERIC_CLOSE_EPITAPH_CANDIDATES),
    "rescued": ("memorial_epitaph_savior", *_GENERIC_CLOSE_EPITAPH_CANDIDATES),
    "friend": _GENERIC_CLOSE_EPITAPH_CANDIDATES,
    "mentor": _GENERIC_CLOSE_EPITAPH_CANDIDATES,
    "disciple": _GENERIC_CLOSE_EPITAPH_CANDIDATES,
    "betrayer": ("memorial_epitaph_rival",),
    "rival": ("memorial_epitaph_rival",),
}
_ALIAS_RELATION_CANDIDATES = {
    "spouse": ("alias_spouse_site", "alias_vigil_site", "alias_rest_site"),
    "family": ("alias_family_site", "alias_vigil_site", "alias_rest_site"),
    "savior": ("alias_savior_site", "alias_vigil_site", "alias_rest_site"),
    "rescued": ("alias_rescued_site", "alias_vigil_site", "alias_rest_site"),
    "friend": ("alias_vigil_site", "alias_rest_site"),
    "mentor": ("alias_vigil_site", "alias_rest_site"),
    "disciple": ("alias_vigil_site", "alias_rest_site"),
    "betrayer": ("alias_fall_site",),
    "rival": ("alias_fall_site",),
}
_CONTEXTUAL_TEMPLATE_REQUIREMENTS: dict[str, Callable[[Optional["NarrativeContext"]], bool]] = {
    "memorial_epitaph_companions": lambda context: context is not None and context.observer_count >= 2,
    "alias_vigil_site": lambda context: context is not None and context.observer_count >= 2,
}


@dataclass(frozen=True)
class NarrativeContext:
    """Narrative selection context derived from relations, reports, and memory."""

    relation_tags: Sequence[str] = field(default_factory=tuple)
    observer_count: int = 0
    yearly_death_count: int = 0
    report_notable_count: int = 0
    location_memorial_count: int = 0
    location_alias_count: int = 0
    location_trace_count: int = 0
    location_rumor_count: int = 0
    subject_rumor_count: int = 0
    world_definition_key: str = ""
    world_display_name: str = ""
    world_era: str = ""
    location_region_type: str = ""

    @property
    def primary_relation_tag(self) -> Optional[str]:
        return _primary_relation_tag(self.relation_tags)

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


def _primary_relation_tag(relation_tags: Sequence[str]) -> Optional[str]:
    for tag in _RELATION_PRIORITY:
        if tag in relation_tags:
            return tag
    return relation_tags[0] if relation_tags else None


def _available_template_candidates(
    candidate_keys: Sequence[str],
    context: Optional["NarrativeContext"],
) -> List[str]:
    candidates: List[str] = []
    for key in candidate_keys:
        requirement = _CONTEXTUAL_TEMPLATE_REQUIREMENTS.get(key)
        if requirement is not None and not requirement(context):
            continue
        if key not in candidates:
            candidates.append(key)
    return candidates


def _choose_candidate_key(
    candidates: Sequence[str],
    template_history: Optional[TemplateHistory],
) -> str:
    if template_history is not None:
        return template_history.choose(candidates)
    return candidates[0]


def _normalize_observers(
    observer: Optional["Character" | Iterable["Character"]],
) -> Sequence["Character"]:
    if observer is None:
        return ()
    if hasattr(observer, "get_relation_tags"):
        return (observer,)
    return tuple(observer)


def _collect_relation_tags(
    observer: Optional["Character" | Iterable["Character"]],
    subject_id: Optional[str],
) -> Sequence[str]:
    if subject_id is None:
        return ()
    relation_tags: List[str] = []
    for item in _normalize_observers(observer):
        for tag in item.get_relation_tags(subject_id):
            if tag not in relation_tags:
                relation_tags.append(tag)
    return tuple(relation_tags)


def derive_relation_hint(
    observers: Optional["Character" | Iterable["Character"]],
    subject_id: Optional[str] = None,
) -> Optional[str]:
    """Return the strongest relation tag, preferring directional observer semantics.

    When ``subject_id`` is provided, relation tags are read directionally from
    living observers toward the subject. When it is omitted, a single-character
    compatibility mode aggregates the character's outbound relation tags.
    """

    if observers is None:
        return None
    if subject_id is None:
        relation_tags = getattr(observers, "relation_tags", None)
        if relation_tags is None:
            return None
        all_tags: List[str] = []
        for tags in relation_tags.values():
            for tag in tags:
                if tag not in all_tags:
                    all_tags.append(tag)
        return _primary_relation_tag(tuple(all_tags))
    return _primary_relation_tag(_collect_relation_tags(observers, subject_id))


def build_narrative_context(
    world: "World",
    location_id: str,
    year: int,
    *,
    observer: Optional["Character" | Iterable["Character"]] = None,
    subject_id: Optional[str] = None,
    yearly_report: Optional["YearlyReport"] = None,
) -> NarrativeContext:
    """Build a minimal PR-I context from relation tags, reports, and world memory.

    Callers that need multiple contexts for the same year can pass a precomputed
    ``yearly_report`` to avoid repeating yearly aggregation work.
    """
    relation_tags = _collect_relation_tags(observer, subject_id)
    observers = _normalize_observers(observer)

    report = yearly_report if yearly_report is not None else generate_yearly_report(world, year)
    location_report = next(
        (entry for entry in report.location_entries if entry.location_id == location_id),
        None,
    )
    location = world.get_location_by_id(location_id)
    world_definition = world.setting_bundle.world_definition if world.setting_bundle is not None else None
    memorials = world.get_memorials_for_location(location_id)
    aliases = list(location.aliases) if location is not None else []
    traces = list(location.live_traces) if location is not None else []
    active_rumor_count = sum(
        1
        for rumor in world.rumors
        if rumor.source_location_id == location_id and not rumor.is_expired
    )
    subject_rumor_count = sum(
        1
        for rumor in world.rumors
        if (
            rumor.source_location_id == location_id
            and not rumor.is_expired
            and subject_id is not None
            and rumor.target_subject == subject_id
        )
    )
    notable_count = len(location_report.notable_events) if location_report is not None else 0
    return NarrativeContext(
        relation_tags=relation_tags,
        observer_count=len(observers),
        yearly_death_count=report.deaths_this_year,
        report_notable_count=notable_count,
        location_memorial_count=len(memorials),
        location_alias_count=len(aliases),
        location_trace_count=len(traces),
        location_rumor_count=active_rumor_count,
        subject_rumor_count=subject_rumor_count,
        world_definition_key=world_definition.world_key if world_definition is not None else "",
        world_display_name=world_definition.display_name if world_definition is not None else world.name,
        world_era=world_definition.era if world_definition is not None else "",
        location_region_type=location.region_type if location is not None else "",
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


def choose_epitaph_template_key(
    cause: str,
    char: Optional["Character"] = None,
    template_history: Optional[TemplateHistory] = None,
    relation_hint: Optional[str] = None,
    title_hint: Optional[str] = None,
    favorite: bool = False,
    context: Optional[NarrativeContext] = None,
) -> str:
    """Choose the memorial epitaph template key before rendering text."""
    candidates: List[str] = []
    active_relation = relation_hint or (context.primary_relation_tag if context else None)
    if active_relation in _EPITAPH_RELATION_CANDIDATES:
        candidates.extend(_available_template_candidates(_EPITAPH_RELATION_CANDIDATES[active_relation], context))
    elif favorite or title_hint:
        candidates.extend(_available_template_candidates(_GENERIC_CLOSE_EPITAPH_CANDIDATES, context))
    elif context is not None and context.is_tragic_site and context.world_era:
        candidates.append("memorial_epitaph_era")
    elif context is not None and context.is_tragic_site:
        candidates.append("memorial_epitaph_tragic_year")
    elif context is not None and context.subject_rumor_count >= 2:
        candidates.append("memorial_epitaph_whispered")

    # If no relation- or tragedy-specific tone applies, the job/cause fallbacks
    # below still guarantee at least one candidate before selection happens.
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

    return _choose_candidate_key(candidates, template_history)


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
    key = choose_epitaph_template_key(
        cause,
        char=char,
        template_history=template_history,
        relation_hint=relation_hint,
        title_hint=title_hint,
        favorite=favorite,
        context=context,
    )
    return tr(
        key,
        name=char_name,
        year=year,
        location=location_name,
        era=context.world_era if context is not None else "",
    )


def choose_alias_template_key(
    event_kind: str,
    template_history: Optional[TemplateHistory] = None,
    relation_hint: Optional[str] = None,
    context: Optional[NarrativeContext] = None,
) -> str:
    """Choose the location alias template key before rendering text."""
    candidates: List[str] = []
    active_relation = relation_hint or (context.primary_relation_tag if context else None)
    if event_kind in EVENT_KINDS_FATAL:
        if active_relation in _ALIAS_RELATION_CANDIDATES:
            candidates.extend(_available_template_candidates(_ALIAS_RELATION_CANDIDATES[active_relation], context))
        if context is not None and context.location_memorial_count >= 1:
            candidates.append("alias_memorial_site")
        if context is not None and context.subject_rumor_count >= 2:
            candidates.append("alias_whisper_site")
        if context is not None and context.location_trace_count >= 3:
            candidates.append("alias_fallen_path")
        elif context is not None and context.world_era and context.location_alias_count >= 1:
            candidates.append("alias_echo_site")
        candidates.append("alias_death_site")
    else:
        candidates.append("alias_notable_site")
    return _choose_candidate_key(candidates, template_history)


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
    key = choose_alias_template_key(
        event_kind,
        template_history=template_history,
        relation_hint=relation_hint,
        context=context,
    )
    return tr(key, name=char_name)
