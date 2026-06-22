"""Cause-aware linguistic law candidates for historical language evolution."""

from __future__ import annotations

from typing import Iterable, List

from ..content.setting_bundle import LanguageDefinition
from .schema import SoundChangeRuleDefinition


_CONTACT_CAUSE_MARKERS = (
    "occupation",
    "war",
    "battle",
    "faction",
    "border",
    "truce",
    "trade",
    "market",
)
_ISOLATION_CAUSE_MARKERS = (
    "route_blocked",
    "route_closed",
    "blockade",
    "siege",
    "isolated",
)
_PRESTIGE_CAUSE_MARKERS = (
    "era",
    "civilization",
    "rename",
    "decree",
    "capital",
    "official",
)


def law_candidates_for_cause(
    language: LanguageDefinition,
    *,
    cause_key: str = "",
    sequence_index: int = 0,
) -> List[SoundChangeRuleDefinition]:
    """Return deterministic sound laws motivated by a historical cause."""
    cause_group = _cause_group(cause_key)
    if not cause_group:
        return []
    rule_specs = {
        "contact": _contact_laws,
        "isolation": _isolation_laws,
        "prestige": _prestige_laws,
    }[cause_group]()
    return [
        _rule(
            language.language_key,
            cause_group,
            index,
            source=source,
            target=target,
            before=before,
            after=after,
            position=position,
            description=description,
            sequence_index=sequence_index,
            weight=weight,
        )
        for index, (source, target, before, after, position, description, weight) in enumerate(rule_specs)
    ]


def lexical_bias_for_cause(cause_key: str) -> tuple[str, str]:
    """Return name-stem and toponym-suffix hints for cause-shaped vocabulary."""
    cause_group = _cause_group(cause_key)
    if cause_group == "contact":
        return "ven", "var"
    if cause_group == "isolation":
        return "tor", "hold"
    if cause_group == "prestige":
        return "ael", "ion"
    return "", ""


def _cause_group(cause_key: str) -> str:
    lowered = cause_key.lower()
    if _contains_any(lowered, _ISOLATION_CAUSE_MARKERS):
        return "isolation"
    if _contains_any(lowered, _CONTACT_CAUSE_MARKERS):
        return "contact"
    if _contains_any(lowered, _PRESTIGE_CAUSE_MARKERS):
        return "prestige"
    return ""


def _contains_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


def _contact_laws() -> list[tuple[str, str, str, str, str, str, int]]:
    return [
        (
            "t",
            "d",
            "vowel",
            "vowel",
            "medial",
            "Contact lenition: frequent bilingual use weakens intervocalic /t/ to /d/.",
            4,
        ),
        (
            "k",
            "g",
            "vowel",
            "vowel",
            "medial",
            "Contact lenition: prestige speech voices intervocalic /k/ to /g/.",
            3,
        ),
        (
            "s",
            "z",
            "vowel",
            "vowel",
            "medial",
            "Contact voicing: borrowed cadence voices intervocalic /s/.",
            2,
        ),
        (
            "p",
            "v",
            "vowel",
            "vowel",
            "medial",
            "Contact lenition: trade pidgin use spirantizes intervocalic /p/.",
            2,
        ),
    ]


def _isolation_laws() -> list[tuple[str, str, str, str, str, str, int]]:
    return [
        (
            "t",
            "ts",
            "",
            "",
            "initial",
            "Isolation fortition: closed-route dialects affricate initial /t/.",
            4,
        ),
        (
            "d",
            "t",
            "",
            "",
            "final",
            "Isolation final devoicing: disconnected settlements harden final /d/.",
            3,
        ),
        (
            "a",
            "o",
            "",
            "nasal",
            "any",
            "Isolation backing: local nasal environments pull /a/ toward /o/.",
            2,
        ),
        (
            "r",
            "rh",
            "",
            "",
            "initial",
            "Isolation rhotacism: frontier speech strengthens initial /r/.",
            2,
        ),
    ]


def _prestige_laws() -> list[tuple[str, str, str, str, str, str, int]]:
    return [
        (
            "k",
            "ch",
            "",
            "front_vowel",
            "any",
            "Prestige palatalization: courtly naming fronts /k/ before front vowels.",
            4,
        ),
        (
            "g",
            "y",
            "",
            "front_vowel",
            "any",
            "Prestige palatalization: official diction turns /g/ to a glide before front vowels.",
            3,
        ),
        (
            "e",
            "i",
            "",
            "",
            "final",
            "Prestige vowel raising: fashionable final /e/ rises to /i/.",
            2,
        ),
        (
            "s",
            "sh",
            "",
            "front_vowel",
            "any",
            "Prestige sibilant shift: ceremonial forms palatalize /s/ before front vowels.",
            2,
        ),
    ]


def _rule(
    language_key: str,
    cause_group: str,
    index: int,
    *,
    source: str,
    target: str,
    before: str,
    after: str,
    position: str,
    description: str,
    sequence_index: int,
    weight: int,
) -> SoundChangeRuleDefinition:
    return SoundChangeRuleDefinition(
        rule_key=f"law:{language_key}:{cause_group}:{sequence_index}:{index}:{source}>{target}",
        source=source,
        target=target,
        before=before,
        after=after,
        position=position,
        description=description,
        weight=weight,
    )
