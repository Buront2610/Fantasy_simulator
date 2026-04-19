"""Historically-inspired rule presets for language evolution."""

from __future__ import annotations

from typing import Dict, List

from .schema import SoundChangeRuleDefinition


PRESET_EVOLUTION_RULES: Dict[str, List[SoundChangeRuleDefinition]] = {
    "romance_like": [
        SoundChangeRuleDefinition(
            rule_key="romance_like.intervocalic_t_voicing",
            source="t",
            target="d",
            before="vowel",
            after="vowel",
            position="medial",
            description="Intervocalic lenition inspired by Romance developments.",
            weight=3,
        ),
        SoundChangeRuleDefinition(
            rule_key="romance_like.k_before_front_vowel",
            source="k",
            target="ch",
            after="front_vowel",
            description="Palatalization before front vowels.",
            weight=2,
        ),
    ],
    "celtic_like": [
        SoundChangeRuleDefinition(
            rule_key="celtic_like.intervocalic_d_lenition",
            source="d",
            target="dh",
            before="vowel",
            after="vowel",
            position="medial",
            description="Intervocalic lenition inspired by Celtic consonant mutation.",
            weight=3,
        ),
        SoundChangeRuleDefinition(
            rule_key="celtic_like.r_to_l_medial",
            source="r",
            target="l",
            before="vowel",
            after="vowel",
            position="medial",
            description="Liquid drift in internal syllables.",
            weight=2,
        ),
    ],
    "germanic_like": [
        SoundChangeRuleDefinition(
            rule_key="germanic_like.i_umlaut_a",
            source="a",
            target="e",
            after="front_vowel",
            description="Fronting reminiscent of i-mutation.",
            weight=2,
        ),
        SoundChangeRuleDefinition(
            rule_key="germanic_like.g_to_y_before_front_vowel",
            source="g",
            target="y",
            after="front_vowel",
            description="Palatal glide development before front vowels.",
            weight=2,
        ),
    ],
    "turkic_like": [
        SoundChangeRuleDefinition(
            rule_key="turkic_like.o_rounding",
            source="o",
            target="ou",
            description="Rounded vowel expansion inspired by steppe vowel shifts.",
            weight=2,
        ),
        SoundChangeRuleDefinition(
            rule_key="turkic_like.g_lenition",
            source="g",
            target="gh",
            before="vowel",
            after="vowel",
            position="medial",
            description="Medial lenition common in several steppe phonologies.",
            weight=2,
        ),
    ],
}
