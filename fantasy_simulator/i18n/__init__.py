"""fantasy_simulator.i18n - Localization sub-package."""

from .engine import get_locale, normalize_locale, set_locale, tr, tr_for_locale, tr_term, tr_term_for_locale

__all__ = [
    "get_locale",
    "normalize_locale",
    "set_locale",
    "tr",
    "tr_for_locale",
    "tr_term",
    "tr_term_for_locale",
]
