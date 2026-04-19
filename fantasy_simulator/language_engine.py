"""Backward-compatible import shim for the language package."""

from .language.engine import GeneratedLanguageProfile, LanguageEngine

__all__ = ["GeneratedLanguageProfile", "LanguageEngine"]
