"""Character assembly routines for random and template creation."""

from __future__ import annotations

import random
from typing import Any, Callable, Dict, Sequence

from .character import Character, random_stats
from .character_creator_naming import GENDERS, random_name
from .character_templates import TEMPLATES
from .content.setting_bundle import NamingRulesDefinition
from .i18n import tr, tr_term


NamingRulesResolver = Callable[..., NamingRulesDefinition]


def add_origin_history(char: Character) -> None:
    """Attach the localized birth history line shared by creation paths."""
    char.add_history(tr("history_born_into_world", race=tr_term(char.race), job=tr_term(char.job)))


def create_random_character(
    *,
    race_entries: Sequence[tuple[str, str, Dict[str, int]]],
    job_entries: Sequence[tuple[str, str, list[str]]],
    naming_rules_for_identity: NamingRulesResolver,
    extra_skill_pool: Sequence[str],
    name: str | None = None,
    rng: Any = random,
    tribe: str | None = None,
    region: str | None = None,
) -> Character:
    """Build a random character from resolved race/job catalogs."""
    gender = rng.choice(GENDERS)
    race_entry = rng.choice(list(race_entries))
    race = race_entry[0]
    race_bonuses = race_entry[2]

    job_entry = rng.choice(list(job_entries))
    job = job_entry[0]
    job_skills = job_entry[2]

    age = rng.randint(16, 55)
    char_name = name or random_name(
        gender,
        naming_rules_for_identity(race=race, tribe=tribe, region=region),
        rng=rng,
    )
    stats = random_stats(base=25, spread=45, race_bonuses=race_bonuses, rng=rng)

    skills: Dict[str, int] = {}
    for skill in job_skills:
        skills[skill] = rng.randint(1, 3)
    extra_skills = rng.sample(list(extra_skill_pool), k=min(2, len(extra_skill_pool)))
    for skill in extra_skills:
        if skill not in skills:
            skills[skill] = 1

    char_rng = rng if isinstance(rng, random.Random) else None
    char = Character(
        name=char_name,
        age=age,
        gender=gender,
        race=race,
        job=job,
        skills=skills,
        rng=char_rng,
        **stats,
    )
    add_origin_history(char)
    return char


def create_template_character(
    *,
    template_name: str,
    naming_rules_for_identity: NamingRulesResolver,
    name: str | None = None,
    rng: Any = random,
    tribe: str | None = None,
    region: str | None = None,
) -> Character:
    """Build a character from a built-in Aethoria template."""
    key = template_name.lower().strip()
    if key not in TEMPLATES:
        available = ", ".join(TEMPLATES.keys())
        raise ValueError(f"Unknown template '{template_name}'. Available: {available}")

    template = TEMPLATES[key]
    race = template["race"]
    job = template["job"]
    gender = rng.choice(GENDERS)
    char_name = name or random_name(
        gender,
        naming_rules_for_identity(race=race, tribe=tribe, region=region),
        rng=rng,
    )
    age = rng.randint(20, 40)
    stats = {stat: max(1, min(100, value + rng.randint(-5, 5))) for stat, value in template["base_stats"].items()}
    skills = dict(template["skills"])

    char_rng = rng if isinstance(rng, random.Random) else None
    char = Character(
        name=char_name,
        age=age,
        gender=gender,
        race=race,
        job=job,
        skills=skills,
        rng=char_rng,
        **stats,
    )
    add_origin_history(char)
    return char
