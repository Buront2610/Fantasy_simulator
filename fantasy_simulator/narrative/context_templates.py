"""Template selection and rendering helpers for narrative context text."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional, Sequence

from ..i18n import tr
from .constants import (
    EVENT_KIND_ADVENTURE_DEATH,
    EVENT_KINDS_FATAL,
)
from .context_models import NarrativeContext
from .template_history import TemplateHistory

if TYPE_CHECKING:
    from ..character import Character


GENERIC_CLOSE_EPITAPH_CANDIDATES = ("memorial_epitaph_companions", "memorial_epitaph_beloved")
EPITAPH_RELATION_CANDIDATES = {
    "spouse": ("memorial_epitaph_spouse", *GENERIC_CLOSE_EPITAPH_CANDIDATES),
    "family": ("memorial_epitaph_family", *GENERIC_CLOSE_EPITAPH_CANDIDATES),
    "savior": ("memorial_epitaph_savior", *GENERIC_CLOSE_EPITAPH_CANDIDATES),
    "rescued": ("memorial_epitaph_savior", *GENERIC_CLOSE_EPITAPH_CANDIDATES),
    "friend": GENERIC_CLOSE_EPITAPH_CANDIDATES,
    "mentor": GENERIC_CLOSE_EPITAPH_CANDIDATES,
    "disciple": GENERIC_CLOSE_EPITAPH_CANDIDATES,
    "betrayer": ("memorial_epitaph_rival",),
    "rival": ("memorial_epitaph_rival",),
}
ALIAS_RELATION_CANDIDATES = {
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
CONTEXTUAL_TEMPLATE_REQUIREMENTS: dict[str, Callable[[Optional[NarrativeContext]], bool]] = {
    "memorial_epitaph_companions": lambda context: context is not None and context.observer_count >= 2,
    "alias_vigil_site": lambda context: context is not None and context.observer_count >= 2,
}

# Combat-oriented jobs -> warrior epitaph
COMBAT_JOBS: frozenset = frozenset({
    "Warrior", "Knight", "Paladin", "Ranger", "Mercenary",
})

# Magic / knowledge-oriented jobs -> mage epitaph
MAGIC_JOBS: frozenset = frozenset({
    "Mage", "Witch", "Healer", "Sage", "Druid", "Bard",
})


def available_template_candidates(
    candidate_keys: Sequence[str],
    context: Optional[NarrativeContext],
) -> List[str]:
    candidates: List[str] = []
    for key in candidate_keys:
        requirement = CONTEXTUAL_TEMPLATE_REQUIREMENTS.get(key)
        if requirement is not None and not requirement(context):
            continue
        if key not in candidates:
            candidates.append(key)
    return candidates


def choose_candidate_key(
    candidates: Sequence[str],
    template_history: Optional[TemplateHistory],
) -> str:
    if template_history is not None:
        return template_history.choose(candidates)
    return candidates[0]


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
    if active_relation in EPITAPH_RELATION_CANDIDATES:
        candidates.extend(available_template_candidates(EPITAPH_RELATION_CANDIDATES[active_relation], context))
    elif favorite or title_hint:
        candidates.extend(available_template_candidates(GENERIC_CLOSE_EPITAPH_CANDIDATES, context))
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
        if job in COMBAT_JOBS:
            candidates.append("memorial_epitaph_warrior")
        elif job in MAGIC_JOBS:
            candidates.append("memorial_epitaph_mage")

    if cause in (EVENT_KIND_ADVENTURE_DEATH, "death_cause_dungeon"):
        candidates.extend(["memorial_epitaph_adventurer", "memorial_epitaph_default"])
    else:
        candidates.extend(["memorial_epitaph_default", "memorial_epitaph_adventurer"])

    return choose_candidate_key(candidates, template_history)


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
    the character's job. When *char* is None (e.g. during legacy data
    migration), falls back to the adventurer or default template.
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
        if active_relation in ALIAS_RELATION_CANDIDATES:
            candidates.extend(available_template_candidates(ALIAS_RELATION_CANDIDATES[active_relation], context))
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
    return choose_candidate_key(candidates, template_history)


def alias_for_event(
    event_kind: str,
    char_name: str,
    location_name: str,
    template_history: Optional[TemplateHistory] = None,
    relation_hint: Optional[str] = None,
    context: Optional[NarrativeContext] = None,
) -> str:
    """Return a location alias string generated from a significant event."""
    key = choose_alias_template_key(
        event_kind,
        template_history=template_history,
        relation_hint=relation_hint,
        context=context,
    )
    return tr(key, name=char_name)
