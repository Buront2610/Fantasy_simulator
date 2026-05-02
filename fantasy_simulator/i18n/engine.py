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


def normalize_locale(locale: str | None) -> str:
    if locale is None:
        return _LOCALE
    return locale if locale in _TEXT else "en"


def tr_for_locale(locale: str | None, key: str, **kwargs: object) -> str:
    resolved_locale = normalize_locale(locale)
    table = _TEXT.get(resolved_locale, _TEXT["en"])
    fallback = _TEXT["en"]
    template = table.get(key, fallback.get(key, key))
    return template.format(**kwargs)


def tr_term_for_locale(locale: str | None, term: str) -> str:
    table = _TERMS.get(normalize_locale(locale), {})
    return table.get(term, term)


def tr(key: str, **kwargs: object) -> str:
    return tr_for_locale(_LOCALE, key, **kwargs)


def tr_term(term: str) -> str:
    return tr_term_for_locale(_LOCALE, term)
