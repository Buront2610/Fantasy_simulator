"""
character_creator.py - Interactive and programmatic character creation.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .character import Character, random_stats
from .i18n import tr
from .content.world_data import JOBS, RACES, ALL_SKILLS

if TYPE_CHECKING:
    from .ui.ui_context import UIContext


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

_FIRST_NAMES_M = [
    "Aldric", "Bram", "Caius", "Dorian", "Eryn", "Faolan",
    "Gareth", "Hadrin", "Ilyan", "Jorin", "Kaelen", "Lorcan",
    "Marek", "Nolan", "Oswin", "Perrin", "Quinn", "Rodric",
    "Soren", "Theron", "Ulric", "Varis", "Westan", "Xander", "Yoren", "Zephyr",
]
_FIRST_NAMES_F = [
    "Aelindra", "Brynn", "Casia", "Dael", "Eira", "Feyra",
    "Gwynne", "Halia", "Isara", "Jessa", "Kira", "Lyra",
    "Mira", "Nissa", "Orla", "Petra", "Quellyn", "Rhea",
    "Sable", "Talia", "Ursa", "Vela", "Wren", "Xara", "Ysmay", "Zara",
]
_FIRST_NAMES_NB = _FIRST_NAMES_M + _FIRST_NAMES_F
_LAST_NAMES = [
    "Ashwood", "Blackthorn", "Coldwater", "Dawnbringer", "Emberveil",
    "Frostmantle", "Goldvein", "Hawkridge", "Ironforge", "Jadewood",
    "Kindlewick", "Lightborn", "Moonwhisper", "Nightshade", "Oakheart",
    "Proudmoor", "Quicksilver", "Riverstone", "Shadowmere", "Thornwall",
    "Underhill", "Voidwalker", "Windmere", "Yarrow", "Zephyrhaven",
]


def _random_name(gender: str, rng: Any = random) -> str:
    if gender == "Male":
        first = rng.choice(_FIRST_NAMES_M)
    elif gender == "Female":
        first = rng.choice(_FIRST_NAMES_F)
    else:
        first = rng.choice(_FIRST_NAMES_NB)
    last = rng.choice(_LAST_NAMES)
    return f"{first} {last}"


class CharacterCreator:
    """Factory for creating Character instances."""

    def create_interactive(self, ctx: "UIContext | None" = None) -> Character:
        from .ui.ui_context import _default_ctx
        ctx = _default_ctx(ctx)
        out = ctx.out

        out.print_line()
        out.print_separator("=", 50)
        out.print_line(f"  {tr('interactive_character_creation')}")
        out.print_separator("=", 50)

        name = self._prompt(tr("enter_character_name"), default=_random_name("Non-binary"), ctx=ctx)
        gender = self._prompt_choice(tr("choose_gender"), _GENDERS, default="Non-binary", ctx=ctx)

        race_names = [r[0] for r in RACES]
        out.print_line(f"\n  {tr('available_races')}:")
        for i, (rname, rdesc, _) in enumerate(RACES, 1):
            out.print_line(f"  {i}. {rname:12s} - {rdesc[:60]}...")
        race = self._prompt_choice(tr("choose_race"), race_names, default=race_names[0], ctx=ctx)

        job_names = [j[0] for j in JOBS]
        out.print_line(f"\n  {tr('available_jobs')}:")
        for i, (jname, jdesc, _) in enumerate(JOBS, 1):
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

        race_bonuses = next((r[2] for r in RACES if r[0] == race), {})
        for stat, bonus in race_bonuses.items():
            if stat in stats:
                stats[stat] = Character._clamp(stats[stat] + bonus)

        job_skills_raw = next((j[2] for j in JOBS if j[0] == job), [])
        skills = {s: 1 for s in job_skills_raw}

        char = Character(name=name, age=age, gender=gender, race=race, job=job, skills=skills, **stats)
        char.add_history(f"Born into the world as a {race} {job}.")
        out.print_line(f"\n  {tr('character_created')}")
        out.print_line(char.stat_block())
        return char

    def create_random(self, name: Optional[str] = None, rng: Any = random) -> Character:
        gender = rng.choice(_GENDERS)
        race_entry = rng.choice(RACES)
        race = race_entry[0]
        race_bonuses = race_entry[2]

        job_entry = rng.choice(JOBS)
        job = job_entry[0]
        job_skills = job_entry[2]

        age = rng.randint(16, 55)
        char_name = name or _random_name(gender, rng=rng)
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
        char.add_history(f"Born into the world as a {race} {job}.")
        return char

    def create_from_template(self, template_name: str, name: Optional[str] = None, rng: Any = random) -> Character:
        key = template_name.lower().strip()
        if key not in _TEMPLATES:
            available = ", ".join(_TEMPLATES.keys())
            raise ValueError(f"Unknown template '{template_name}'. Available: {available}")

        tmpl = _TEMPLATES[key]
        race = tmpl["race"]
        job = tmpl["job"]
        gender = rng.choice(_GENDERS)
        char_name = name or _random_name(gender, rng=rng)
        age = rng.randint(20, 40)

        stats = {k: max(1, min(100, v + rng.randint(-5, 5))) for k, v in tmpl["base_stats"].items()}
        skills = dict(tmpl["skills"])

        char_rng = rng if isinstance(rng, random.Random) else None
        char = Character(
            name=char_name, age=age, gender=gender, race=race, job=job,
            skills=skills, rng=char_rng, **stats,
        )
        char.add_history(f"Born into the world as a {race} {job}.")
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
        total_points = 60

        raw = ctx.inp.read_line(f"  > {tr('manually_distribute_stats')}: ").strip().lower()
        if raw != "y":
            return defaults

        allocated: Dict[str, int] = {}
        for i, stat in enumerate(stat_names):
            left = total_points - sum(allocated.values())
            remaining_stats = len(stat_names) - i
            max_allowed = min(40, left - (remaining_stats - 1) * 10)
            while True:
                raw_val = ctx.inp.read_line(f"  > {stat.capitalize():15s} (10-40, {left} pts left): ").strip()
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
                if left - val < (remaining_stats - 1) * 10:
                    ctx.out.print_line(f"  {tr('not_enough_points_left', max_allowed=max_allowed)}")
                    continue
                allocated[stat] = val
                break
        return allocated

    @staticmethod
    def list_templates() -> List[str]:
        return list(_TEMPLATES.keys())
