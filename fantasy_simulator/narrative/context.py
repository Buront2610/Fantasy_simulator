"""
narrative/context.py - Minimal NarrativeContext for world memory generation.

PR-F: Provides just enough context-aware text selection for memorial
epitaphs and location aliases.  Full NarrativeContext expansion
(relation tags, reports, world memory integration) is deferred to PR-H.

Design §E-2: "NarrativeContext 導入前でも最低限のテンプレート選択で
memorial / alias テキストを安定生成する"
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

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
    if char is not None:
        job = getattr(char, "job", "")
        if job in _COMBAT_JOBS:
            key = "memorial_epitaph_warrior"
            if template_history is not None:
                key = template_history.choose([key, "memorial_epitaph_adventurer"])
            return tr(key, name=char_name, year=year, location=location_name)
        if job in _MAGIC_JOBS:
            key = "memorial_epitaph_mage"
            if template_history is not None:
                key = template_history.choose([key, "memorial_epitaph_adventurer"])
            return tr(key, name=char_name, year=year, location=location_name)

    if cause in (EVENT_KIND_ADVENTURE_DEATH, "death_cause_dungeon"):
        key = "memorial_epitaph_adventurer"
        if template_history is not None:
            key = template_history.choose([key, "memorial_epitaph_default"])
        return tr(key, name=char_name, year=year, location=location_name)

    key = "memorial_epitaph_default"
    if template_history is not None:
        key = template_history.choose([key, "memorial_epitaph_adventurer"])
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
        key = "alias_death_site"
    else:
        key = "alias_notable_site"
    if template_history is not None:
        key = template_history.choose([key, "alias_notable_site"])
    return tr(key, name=char_name)
