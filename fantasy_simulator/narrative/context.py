"""
narrative/context.py - Minimal NarrativeContext for world memory generation.

PR-F established the minimal template-selection hooks for memorial
epitaphs and location aliases. PR-I starts feeding relation-tag context
into those hooks while keeping the API small and deterministic.

Design §E-2: "NarrativeContext 導入前でも最低限のテンプレート選択で
memorial / alias テキストを安定生成する"
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Optional, Tuple

from ..i18n import tr
from .constants import (
    EVENT_KIND_ADVENTURE_DEATH,
    EVENT_KIND_BATTLE_FATAL,
    EVENT_KIND_DEATH,
)
from .template_history import TemplateHistory

if TYPE_CHECKING:
    from ..character import Character

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

_RELATION_PRIORITY: Tuple[str, ...] = (
    "spouse",
    "savior",
    "friend",
    "betrayer",
    "rival",
)

_RELATION_EPITAPH_KEYS = {
    "spouse": "memorial_epitaph_cherished",
    "savior": "memorial_epitaph_cherished",
    "friend": "memorial_epitaph_cherished",
    "betrayer": "memorial_epitaph_contested",
    "rival": "memorial_epitaph_contested",
}

_RELATION_ALIAS_KEYS = {
    "spouse": "alias_rest_site",
    "savior": "alias_rest_site",
    "friend": "alias_rest_site",
    "betrayer": "alias_fall_site",
    "rival": "alias_fall_site",
}


def derive_relation_hint(
    observers: Optional[Iterable["Character"] | "Character"],
    subject_id: Optional[str] = None,
) -> Optional[str]:
    """Return the strongest relation tag, preferring directional observer semantics.

    When ``subject_id`` is provided, relation tags are read directionally from
    ``observers -> subject``. This is the preferred PR-I path.

    When ``subject_id`` is omitted, a single-character compatibility mode is used
    and tags are aggregated from that character's outbound relation map.
    """

    if observers is None:
        return None
    if subject_id is None:
        char = observers
        all_tags = {tag for tags in char.relation_tags.values() for tag in tags}
        for tag in _RELATION_PRIORITY:
            if tag in all_tags:
                return tag
        return None
    all_tags = set()
    for observer in observers:
        all_tags.update(observer.get_relation_tags(subject_id))
    for tag in _RELATION_PRIORITY:
        if tag in all_tags:
            return tag
    return None


def _choose_template_key(
    primary_key: str,
    fallback_key: str,
    template_history: Optional[TemplateHistory],
) -> str:
    if template_history is None:
        return primary_key
    return template_history.choose([primary_key, fallback_key])


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
    # Future hook:
    # relation_hint / title_hint / favorite can influence variant weighting
    # once relation_tags and report metadata are fed into NarrativeContext.
    relation_key = _RELATION_EPITAPH_KEYS.get(relation_hint or "")
    if relation_key is not None:
        relation_key = _choose_template_key(
            relation_key,
            "memorial_epitaph_default",
            template_history,
        )
        return tr(relation_key, name=char_name, year=year, location=location_name)

    if char is not None:
        job = getattr(char, "job", "")
        if job in _COMBAT_JOBS:
            key = _choose_template_key(
                "memorial_epitaph_warrior",
                "memorial_epitaph_adventurer",
                template_history,
            )
            return tr(key, name=char_name, year=year, location=location_name)
        if job in _MAGIC_JOBS:
            key = _choose_template_key(
                "memorial_epitaph_mage",
                "memorial_epitaph_adventurer",
                template_history,
            )
            return tr(key, name=char_name, year=year, location=location_name)

    if cause in (EVENT_KIND_ADVENTURE_DEATH, "death_cause_dungeon"):
        key = _choose_template_key(
            "memorial_epitaph_adventurer",
            "memorial_epitaph_default",
            template_history,
        )
        return tr(key, name=char_name, year=year, location=location_name)

    key = _choose_template_key(
        "memorial_epitaph_default",
        "memorial_epitaph_adventurer",
        template_history,
    )
    return tr(key, name=char_name, year=year, location=location_name)


def alias_for_event(
    event_kind: str,
    char_name: str,
    location_name: str,
    template_history: Optional[TemplateHistory] = None,
    relation_hint: Optional[str] = None,
) -> str:
    """Return a location alias string generated from a significant event.

    Args:
        event_kind: The event kind that triggered alias generation,
            e.g. ``"adventure_death"``, ``"battle_fatal"``.
        char_name: The primary character associated with the event.
        location_name: The canonical location name (for context only;
            the alias text is standalone).
    """
    # Future hook:
    # relation_hint can branch into rival/savior/betrayer alias families.
    if event_kind in (EVENT_KIND_ADVENTURE_DEATH, EVENT_KIND_DEATH, EVENT_KIND_BATTLE_FATAL):
        key = _RELATION_ALIAS_KEYS.get(relation_hint or "", "alias_death_site")
    else:
        key = "alias_notable_site"
    key = _choose_template_key(key, "alias_notable_site", template_history)
    return tr(key, name=char_name)
