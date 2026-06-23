"""Founder-generation background snippets for first-generation adventurers."""

from __future__ import annotations

import hashlib
import random
from typing import Any, Dict

from ..i18n import tr


FOUNDER_BACKGROUND_FIELDS: tuple[str, ...] = (
    "family_origin",
    "family_status",
    "upbringing",
    "pre_adventure",
    "reputation",
)

_FAMILY_ORIGINS = (
    "minor_noble",
    "craft_family",
    "farmstead",
    "temple_orphan",
    "merchant_house",
    "soldier_line",
    "unknown_parentage",
)
_FAMILY_STATUSES = (
    "comfortable",
    "fallen",
    "scattered",
    "ordinary",
    "secretive",
    "respected",
)
_UPBRINGINGS = (
    "strict_training",
    "warm_household",
    "lonely_roads",
    "apprenticed_young",
    "self_taught",
    "quiet_village",
)
_PRE_ADVENTURE = (
    "local_guard",
    "wandering_laborer",
    "failed_scholar",
    "family_debt",
    "pilgrim_errand",
    "ordinary_restlessness",
    "minor_scandal",
    "quiet_departure",
)
_REPUTATIONS = (
    "promising",
    "unremarkable",
    "trouble_shadow",
    "dependable",
    "lucky",
    "unproven",
)


def attach_founder_background(character: Any) -> None:
    """Attach a lightweight founder profile and localized history lines."""
    if getattr(character, "founder_background", None):
        return
    background = generate_founder_background(character)
    character.founder_background = background
    character.add_history(render_founder_family_history(background))
    character.add_history(render_founder_career_history(background))


def generate_founder_background(character: Any) -> Dict[str, str]:
    """Generate deterministic background keys without consuming caller RNG state."""
    rng = random.Random(_background_seed(character))
    return {
        "family_origin": rng.choice(_FAMILY_ORIGINS),
        "family_status": rng.choice(_FAMILY_STATUSES),
        "upbringing": rng.choice(_UPBRINGINGS),
        "pre_adventure": rng.choice(_PRE_ADVENTURE),
        "reputation": rng.choice(_REPUTATIONS),
    }


def render_founder_summary(background: Dict[str, str]) -> str:
    return tr(
        "founder_background_summary",
        family_origin=_background_term("family_origin", background),
        family_status=_background_term("family_status", background),
        upbringing=_background_term("upbringing", background),
        pre_adventure=_background_term("pre_adventure", background),
        reputation=_background_term("reputation", background),
    )


def render_founder_family_history(background: Dict[str, str]) -> str:
    return tr(
        "history_founder_family_background",
        family_origin=_background_term("family_origin", background),
        family_status=_background_term("family_status", background),
        upbringing=_background_term("upbringing", background),
    )


def render_founder_career_history(background: Dict[str, str]) -> str:
    return tr(
        "history_founder_career_background",
        pre_adventure=_background_term("pre_adventure", background),
        reputation=_background_term("reputation", background),
    )


def _background_seed(character: Any) -> int:
    parts = (
        str(getattr(character, "char_id", "")),
        str(getattr(character, "name", "")),
        str(getattr(character, "race", "")),
        str(getattr(character, "job", "")),
        str(getattr(character, "age", "")),
    )
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _background_term(field_name: str, background: Dict[str, str]) -> str:
    value = background.get(field_name, "unknown")
    return tr(f"founder_background_{field_name}_{value}")
