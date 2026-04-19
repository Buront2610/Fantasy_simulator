"""
character_creator.py - Interactive and programmatic character creation.
"""

from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .character import Character, random_stats
from .content.setting_bundle import NamingRulesDefinition, SettingBundle, default_aethoria_bundle
from .content.world_data import ALL_SKILLS
from .i18n import tr, tr_term
from .language_engine import LanguageEngine

if TYPE_CHECKING:
    from .ui.ui_context import UIContext


# Compatibility fixtures for the default Aethoria bundle.
_TEMPLATES: Dict[str, Dict] = {
    "warrior": {
        "race": "Human",
        "job": "Warrior",
        "base_stats": {
            "strength": 70, "intelligence": 30, "dexterity": 55,
            "wisdom": 35, "charisma": 40, "constitution": 70,
        },
        "skills": {"Swordsmanship": 3, "Shield Block": 2, "Battle Cry": 1, "Endurance": 2},
    },
    "mage": {
        "race": "Elf",
        "job": "Mage",
        "base_stats": {
            "strength": 25, "intelligence": 80, "dexterity": 55,
            "wisdom": 65, "charisma": 45, "constitution": 30,
        },
        "skills": {"Fireball": 3, "Mana Control": 3, "Spellcraft": 2, "Arcane Shield": 1},
    },
    "rogue": {
        "race": "Halfling",
        "job": "Rogue",
        "base_stats": {
            "strength": 40, "intelligence": 55, "dexterity": 80,
            "wisdom": 45, "charisma": 55, "constitution": 45,
        },
        "skills": {"Stealth": 4, "Backstab": 3, "Lockpicking": 2, "Evasion": 3},
    },
    "healer": {
        "race": "Human",
        "job": "Healer",
        "base_stats": {
            "strength": 30, "intelligence": 55, "dexterity": 45,
            "wisdom": 75, "charisma": 60, "constitution": 55,
        },
        "skills": {"Holy Light": 3, "Regeneration": 2, "Purify": 2, "Blessing": 1},
    },
    "merchant": {
        "race": "Halfling",
        "job": "Merchant",
        "base_stats": {
            "strength": 30, "intelligence": 65, "dexterity": 50,
            "wisdom": 55, "charisma": 80, "constitution": 40,
        },
        "skills": {"Appraisal": 3, "Bargaining": 4, "Trade Routes": 2, "Persuasion": 3},
    },
    "paladin": {
        "race": "Dragonborn",
        "job": "Paladin",
        "base_stats": {
            "strength": 65, "intelligence": 45, "dexterity": 45,
            "wisdom": 65, "charisma": 55, "constitution": 65,
        },
        "skills": {"Holy Strike": 3, "Divine Shield": 2, "Lay on Hands": 2, "Aura of Courage": 1},
    },
    "druid": {
        "race": "Elf",
        "job": "Druid",
        "base_stats": {
            "strength": 40, "intelligence": 60, "dexterity": 55,
            "wisdom": 70, "charisma": 50, "constitution": 50,
        },
        "skills": {"Nature's Wrath": 3, "Wild Shape": 2, "Commune": 3, "Entangle": 2},
    },
}

_GENDERS = ["Male", "Female", "Non-binary"]
_TEMPLATE_REQUIRED_IDENTITIES = {
    (template["race"], template["job"])
    for template in _TEMPLATES.values()
}


def _random_name(gender: str, naming_rules: NamingRulesDefinition, rng: Any = random) -> str:
    if gender == "Male":
        first = rng.choice(naming_rules.first_names_male)
    elif gender == "Female":
        first = rng.choice(naming_rules.first_names_female)
    else:
        first = rng.choice(naming_rules.first_names_non_binary)
    last = rng.choice(naming_rules.last_names)
    return f"{first} {last}"


class CharacterCreator:
    """Factory for creating Character instances."""

    def __init__(self, setting_bundle: SettingBundle | None = None) -> None:
        self.setting_bundle = setting_bundle
        self._fallback_bundle: SettingBundle | None = None
        self._language_engine: LanguageEngine | None = None
        self._language_engine_signature: str = ""

    def _default_bundle(self) -> SettingBundle:
        """Return a cached default bundle snapshot for compatibility fallbacks."""
        if self._fallback_bundle is None:
            self._fallback_bundle = default_aethoria_bundle()
        return self._fallback_bundle

    def _effective_bundle(self) -> SettingBundle:
        """Return the active bundle for race/job/name lookup."""
        return self.setting_bundle if self.setting_bundle is not None else self._default_bundle()

    @staticmethod
    def _supports_aethoria_projection_fallback(bundle: SettingBundle) -> bool:
        """Return whether empty race/job lists may fall back to Aethoria defaults."""
        return bundle.world_definition.world_key == "aethoria"

    @property
    def naming_rules(self) -> NamingRulesDefinition:
        default_rules = self._default_bundle().world_definition.naming_rules
        bundle = self._effective_bundle()
        rules = bundle.world_definition.naming_rules
        male = list(rules.first_names_male or default_rules.first_names_male)
        female = list(rules.first_names_female or default_rules.first_names_female)
        non_binary = list(rules.first_names_non_binary or (male + female) or default_rules.first_names_non_binary)
        last_names = list(rules.last_names or default_rules.last_names)
        return NamingRulesDefinition(
            first_names_male=male,
            first_names_female=female,
            first_names_non_binary=non_binary,
            last_names=last_names,
        )

    def naming_rules_for_identity(
        self,
        *,
        race: str | None = None,
        tribe: str | None = None,
        region: str | None = None,
    ) -> NamingRulesDefinition:
        language_rules = self._language_engine_for_bundle().naming_rules_for_identity(
            race=race,
            tribe=tribe,
            region=region,
        )
        if language_rules is not None:
            return language_rules
        return self.naming_rules

    def _language_engine_for_bundle(self) -> LanguageEngine:
        bundle = self._effective_bundle()
        signature = json.dumps(
            {
                "languages": [language.to_dict() for language in bundle.world_definition.languages],
                "language_communities": [
                    community.to_dict() for community in bundle.world_definition.language_communities
                ],
            },
            sort_keys=True,
        )
        if self._language_engine is None or self._language_engine_signature != signature:
            self._language_engine = LanguageEngine(bundle.world_definition)
            self._language_engine_signature = signature
        return self._language_engine

    @property
    def race_entries(self) -> List[tuple[str, str, Dict[str, int]]]:
        bundle = self._effective_bundle()
        races = bundle.world_definition.races
        if not races and self._supports_aethoria_projection_fallback(bundle):
            races = self._default_bundle().world_definition.races
        return [
            (race.name, race.description, dict(race.stat_bonuses))
            for race in races
        ]

    @property
    def job_entries(self) -> List[tuple[str, str, List[str]]]:
        bundle = self._effective_bundle()
        jobs = bundle.world_definition.jobs
        if not jobs and self._supports_aethoria_projection_fallback(bundle):
            jobs = self._default_bundle().world_definition.jobs
        return [
            (job.name, job.description, list(job.primary_skills))
            for job in jobs
        ]

    def _require_race_and_job_entries(
        self,
    ) -> tuple[List[tuple[str, str, Dict[str, int]]], List[tuple[str, str, List[str]]]]:
        race_entries = self.race_entries
        job_entries = self.job_entries
        if not race_entries:
            raise ValueError("Setting bundle must define at least one race for character creation")
        if not job_entries:
            raise ValueError("Setting bundle must define at least one job for character creation")
        return race_entries, job_entries

    def _supports_aethoria_templates(self) -> bool:
        if self.setting_bundle is None:
            return True
        if self.setting_bundle.world_definition.world_key != "aethoria":
            return False
        if not self.setting_bundle.world_definition.races and not self.setting_bundle.world_definition.jobs:
            return True
        race_names = {race_name for race_name, _race_desc, _bonuses in self.race_entries}
        job_names = {job_name for job_name, _job_desc, _skills in self.job_entries}
        return all(race in race_names and job in job_names for race, job in _TEMPLATE_REQUIRED_IDENTITIES)

    def list_templates(self) -> List[str]:
        """Return templates supported by the current creator context."""
        if self._supports_aethoria_templates():
            return list(_TEMPLATES.keys())
        return []

    def create_interactive(self, ctx: "UIContext | None" = None) -> Character:
        from .ui.ui_context import _default_ctx
        ctx = _default_ctx(ctx)
        out = ctx.out

        out.print_line()
        out.print_separator("=", 50)
        out.print_line(f"  {tr('interactive_character_creation')}")
        out.print_separator("=", 50)

        name = self._prompt(
            tr("enter_character_name"),
            default=_random_name("Non-binary", self.naming_rules),
            ctx=ctx,
        )
        gender = self._prompt_choice(tr("choose_gender"), _GENDERS, default="Non-binary", ctx=ctx)

        race_entries, job_entries = self._require_race_and_job_entries()
        race_names = [r[0] for r in race_entries]
        out.print_line(f"\n  {tr('available_races')}:")
        for i, (rname, rdesc, _) in enumerate(race_entries, 1):
            out.print_line(f"  {i}. {rname:12s} - {rdesc[:60]}...")
        race = self._prompt_choice(tr("choose_race"), race_names, default=race_names[0], ctx=ctx)

        job_names = [j[0] for j in job_entries]
        out.print_line(f"\n  {tr('available_jobs')}:")
        for i, (jname, jdesc, _) in enumerate(job_entries, 1):
            out.print_line(f"  {i}. {jname:12s} - {jdesc[:60]}...")
        job = self._prompt_choice(tr("choose_job"), job_names, default=job_names[0], ctx=ctx)

        age_str = self._prompt(tr("enter_starting_age"), default="20", ctx=ctx)
        try:
            age = max(15, min(80, int(age_str)))
        except ValueError:
            age = 20

        out.print_line(f"\n  {tr('stat_distribution_info')}")
        out.print_line(f"  {tr('accept_default_stats')}")
        stats = self._allocate_stats(ctx=ctx)

        race_bonuses = next((r[2] for r in race_entries if r[0] == race), {})
        for stat, bonus in race_bonuses.items():
            if stat in stats:
                stats[stat] = Character._clamp(stats[stat] + bonus)

        job_skills_raw = next((j[2] for j in job_entries if j[0] == job), [])
        skills = {s: 1 for s in job_skills_raw}

        char = Character(name=name, age=age, gender=gender, race=race, job=job, skills=skills, **stats)
        char.add_history(tr("history_born_into_world", race=tr_term(race), job=tr_term(job)))
        out.print_line(f"\n  {tr('character_created')}")
        out.print_line(char.stat_block())
        return char

    def create_random(
        self,
        name: Optional[str] = None,
        rng: Any = random,
        *,
        tribe: str | None = None,
        region: str | None = None,
    ) -> Character:
        race_entries, job_entries = self._require_race_and_job_entries()
        gender = rng.choice(_GENDERS)
        race_entry = rng.choice(race_entries)
        race = race_entry[0]
        race_bonuses = race_entry[2]

        job_entry = rng.choice(job_entries)
        job = job_entry[0]
        job_skills = job_entry[2]

        age = rng.randint(16, 55)
        char_name = name or _random_name(
            gender,
            self.naming_rules_for_identity(race=race, tribe=tribe, region=region),
            rng=rng,
        )
        stats = random_stats(base=25, spread=45, race_bonuses=race_bonuses, rng=rng)

        skills: Dict[str, int] = {}
        for s in job_skills:
            skills[s] = rng.randint(1, 3)
        extra_skills = rng.sample(ALL_SKILLS, k=min(2, len(ALL_SKILLS)))
        for s in extra_skills:
            if s not in skills:
                skills[s] = 1

        char_rng = rng if isinstance(rng, random.Random) else None
        char = Character(
            name=char_name, age=age, gender=gender, race=race, job=job,
            skills=skills, rng=char_rng, **stats,
        )
        char.add_history(tr("history_born_into_world", race=tr_term(race), job=tr_term(job)))
        return char

    def create_from_template(
        self,
        template_name: str,
        name: Optional[str] = None,
        rng: Any = random,
        *,
        tribe: str | None = None,
        region: str | None = None,
    ) -> Character:
        key = template_name.lower().strip()
        if not self._supports_aethoria_templates():
            raise ValueError("Character templates are only available for Aethoria-compatible bundles")
        if key not in _TEMPLATES:
            available = ", ".join(_TEMPLATES.keys())
            raise ValueError(f"Unknown template '{template_name}'. Available: {available}")

        tmpl = _TEMPLATES[key]
        race = tmpl["race"]
        job = tmpl["job"]
        gender = rng.choice(_GENDERS)
        char_name = name or _random_name(
            gender,
            self.naming_rules_for_identity(race=race, tribe=tribe, region=region),
            rng=rng,
        )
        age = rng.randint(20, 40)

        stats = {k: max(1, min(100, v + rng.randint(-5, 5))) for k, v in tmpl["base_stats"].items()}
        skills = dict(tmpl["skills"])

        char_rng = rng if isinstance(rng, random.Random) else None
        char = Character(
            name=char_name, age=age, gender=gender, race=race, job=job,
            skills=skills, rng=char_rng, **stats,
        )
        char.add_history(tr("history_born_into_world", race=tr_term(race), job=tr_term(job)))
        return char

    @staticmethod
    def _prompt(message: str, default: str = "", ctx: "UIContext | None" = None) -> str:
        from .ui.ui_context import _default_ctx
        ctx = _default_ctx(ctx)
        display = f"  > {message}"
        if default:
            display += f" [{default}]"
        display += ": "
        raw = ctx.inp.read_line(display).strip()
        return raw if raw else default

    @staticmethod
    def _prompt_choice(message: str, choices: List[str], default: str,
                       ctx: "UIContext | None" = None) -> str:
        from .ui.ui_context import _default_ctx
        ctx = _default_ctx(ctx)
        display = f"  > {message} ({'/'.join(choices)}) [{default}]: "
        while True:
            raw = ctx.inp.read_line(display).strip()
            if not raw:
                return default
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(choices):
                    return choices[idx]
            matches = [c for c in choices if c.lower().startswith(raw.lower())]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                ctx.out.print_line(f"  {tr('ambiguous_choice', matches=', '.join(matches))}")
            else:
                ctx.out.print_line(f"  {tr('invalid_options', choices=', '.join(choices))}")

    @staticmethod
    def _allocate_stats(ctx: "UIContext | None" = None) -> Dict[str, int]:
        from .ui.ui_context import _default_ctx
        ctx = _default_ctx(ctx)
        stat_names = ["strength", "intelligence", "dexterity", "wisdom", "charisma", "constitution"]
        defaults = {s: 10 for s in stat_names}
        extra_points = 60

        raw = ctx.inp.read_line(f"  > {tr('manually_distribute_stats')}: ").strip().lower()
        if raw != "y":
            return defaults

        allocated: Dict[str, int] = dict(defaults)
        for stat in stat_names:
            while True:
                spent_extra = sum(value - 10 for value in allocated.values())
                left_extra = extra_points - spent_extra
                max_allowed = min(40, 10 + left_extra)
                raw_val = ctx.inp.read_line(
                    f"  > {stat.capitalize():15s} (10-{max_allowed}, {left_extra} pts left): "
                ).strip()
                if not raw_val:
                    val = 10
                else:
                    try:
                        val = int(raw_val)
                    except ValueError:
                        ctx.out.print_line(f"  {tr('please_enter_number')}")
                        continue
                if val < 10 or val > max_allowed:
                    ctx.out.print_line(f"  {tr('must_be_between', lo=10, hi=max_allowed)}")
                    continue
                allocated[stat] = val
                break
        return allocated
