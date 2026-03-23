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
    if char is not None:
        job = getattr(char, "job", "")
        if job in _COMBAT_JOBS:
            return tr("memorial_epitaph_warrior", name=char_name, year=year, location=location_name)
        if job in _MAGIC_JOBS:
            return tr("memorial_epitaph_mage", name=char_name, year=year, location=location_name)

    if cause in ("adventure_death", "death_cause_dungeon"):
        return tr("memorial_epitaph_adventurer", name=char_name, year=year, location=location_name)

    return tr("memorial_epitaph_default", name=char_name, year=year, location=location_name)


def alias_for_event(
    event_kind: str,
    char_name: str,
    location_name: str,
) -> str:
    """Return a location alias string generated from a significant event.

    Args:
        event_kind: The event kind that triggered alias generation,
            e.g. ``"adventure_death"``, ``"battle_fatal"``.
        char_name: The primary character associated with the event.
        location_name: The canonical location name (for context only;
            the alias text is standalone).
    """
    if event_kind in ("adventure_death", "death", "battle_fatal"):
        return tr("alias_death_site", name=char_name)
    return tr("alias_notable_site", name=char_name)
