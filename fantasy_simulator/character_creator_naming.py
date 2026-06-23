"""Backward-compatible character creator naming imports."""

from __future__ import annotations

from .character_creator.naming import GENDERS, CharacterCreatorNamingMixin, random_name

__all__ = [
    "GENDERS",
    "CharacterCreatorNamingMixin",
    "random_name",
]
