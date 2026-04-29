"""
narrative/context.py - Public NarrativeContext API for world memory generation.

PR-F established the minimal template-selection hooks for memorial
epitaphs and location aliases. PR-I extends those hooks with relation
tags, yearly reports, and world-memory signals while keeping the API
small and deterministic.

Design §E-2: "NarrativeContext 導入前でも最低限のテンプレート選択で
memorial / alias テキストを安定生成する"
"""

from __future__ import annotations

from .context_builder import build_narrative_context
from .context_models import NarrativeContext
from .context_relations import derive_relation_hint
from .context_templates import (
    alias_for_event,
    choose_alias_template_key,
    choose_epitaph_template_key,
    epitaph_for_character,
)

__all__ = [
    "NarrativeContext",
    "alias_for_event",
    "build_narrative_context",
    "choose_alias_template_key",
    "choose_epitaph_template_key",
    "derive_relation_hint",
    "epitaph_for_character",
]
