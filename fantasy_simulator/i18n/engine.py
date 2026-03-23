"""
i18n/engine.py - Minimal localization helpers for CLI and generated narrative text.
"""

from __future__ import annotations

from typing import Dict

from .ja import TEXT_JA, TERMS_JA
from .en import TEXT_EN, TERMS_EN


_LOCALE = "en"

_TEXT: Dict[str, Dict[str, str]] = {
    "ja": TEXT_JA,
    "en": TEXT_EN,
}

_TERMS: Dict[str, Dict[str, str]] = {
    "ja": TERMS_JA,
    "en": TERMS_EN,
}


def set_locale(locale: str) -> str:
    global _LOCALE
    _LOCALE = locale if locale in _TEXT else "en"
    return _LOCALE


def get_locale() -> str:
    return _LOCALE


def tr(key: str, **kwargs: object) -> str:
    table = _TEXT.get(_LOCALE, _TEXT["en"])
    fallback = _TEXT["en"]
    template = table.get(key, fallback.get(key, key))
    return template.format(**kwargs)


def tr_term(term: str) -> str:
    table = _TERMS.get(_LOCALE, {})
    return table.get(term, term)
