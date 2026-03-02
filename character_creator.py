"""
character_creator.py - Interactive and programmatic character creation.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional

from character import Character, random_stats
from world_data import JOBS, RACES, SKILLS, ALL_SKILLS


# ---------------------------------------------------------------------------
# Pre-built templates
# ---------------------------------------------------------------------------

_TEMPLATES: Dict[str, Dict] = {
    "warrior": {
        "race": "Human",
        "job": "Warrior",
        "base_stats": {"strength": 70, "intelligence": 30, "dexterity": 55,
                       "wisdom": 35, "charisma": 40, "constitution": 70},
        "skills": {"Swordsmanship": 3, "Shield Block": 2, "Battle Cry": 1, "Endurance": 2},
    },
    "mage": {
        "race": "Elf",
        "job": "Mage",
        "base_stats": {"strength": 25, "intelligence": 80, "dexterity": 55,
                       "wisdom": 65, "charisma": 45, "constitution": 30},
        "skills": {"Fireball": 3, "Mana Control": 3, "Spellcraft": 2, "Arcane Shield": 1},
    },
    "rogue": {
        "race": "Halfling",
        "job": "Rogue",
        "base_stats": {"strength": 40, "intelligence": 55, "dexterity": 80,
                       "wisdom": 45, "charisma": 55, "constitution": 45},
        "skills": {"Stealth": 4, "Backstab": 3, "Lockpicking": 2, "Evasion": 3},
    },
    "healer": {
        "race": "Human",
        "job": "Healer",
        "base_stats": {"strength": 30, "intelligence": 55, "dexterity": 45,
                       "wisdom": 75, "charisma": 60, "constitution": 55},
        "skills": {"Holy Light": 3, "Regeneration": 2, "Purify": 2, "Blessing": 1},
    },
    "merchant": {
        "race": "Halfling",
        "job": "Merchant",
        "base_stats": {"strength": 30, "intelligence": 65, "dexterity": 50,
                       "wisdom": 55, "charisma": 80, "constitution": 40},
        "skills": {"Appraisal": 3, "Bargaining": 4, "Trade Routes": 2, "Persuasion": 3},
    },
    "paladin": {
        "race": "Dragonborn",
        "job": "Paladin",
        "base_stats": {"strength": 65, "intelligence": 45, "dexterity": 45,
                       "wisdom": 65, "charisma": 55, "constitution": 65},
        "skills": {"Holy Strike": 3, "Divine Shield": 2, "Lay on Hands": 2, "Aura of Courage": 1},
    },
    "druid": {
        "race": "Elf",
        "job": "Druid",
        "base_stats": {"strength": 40, "intelligence": 60, "dexterity": 55,
                       "wisdom": 70, "charisma": 50, "constitution": 50},
        "skills": {"Nature's Wrath": 3, "Wild Shape": 2, "Commune": 3, "Entangle": 2},
    },
}

_GENDERS = ["Male", "Female", "Non-binary"]

_FIRST_NAMES_M = [
    "Aldric", "Bram", "Caius", "Dorian", "Eryn", "Faolan", "Gareth", "Hadrin",
    "Ilyan", "Jorin", "Kaelen", "Lorcan", "Marek", "Nolan", "Oswin", "Perrin",
    "Quinn", "Rodric", "Soren", "Theron", "Ulric", "Varis", "Westan", "Xander",
    "Yoren", "Zephyr",
]
_FIRST_NAMES_F = [
    "Aelindra", "Brynn", "Casia", "Dael", "Eira", "Feyra", "Gwynne", "Halia",
    "Isara", "Jessa", "Kira", "Lyra", "Mira", "Nissa", "Orla", "Petra",
    "Quellyn", "Rhea", "Sable", "Talia", "Ursa", "Vela", "Wren", "Xara",
    "Ysmay", "Zara",
]
_FIRST_NAMES_NB = _FIRST_NAMES_M + _FIRST_NAMES_F

_LAST_NAMES = [
    "Ashwood", "Blackthorn", "Coldwater", "Dawnbringer", "Emberveil",
    "Frostmantle", "Goldvein", "Hawkridge", "Ironforge", "Jadewood",
    "Kindlewick", "Lightborn", "Moonwhisper", "Nightshade", "Oakheart",
    "Proudmoor", "Quicksilver", "Riverstone", "Shadowmere", "Thornwall",
    "Underhill", "Voidwalker", "Windmere", "Yarrow", "Zephyrhaven",
]


def _random_name(gender: str) -> str:
    if gender == "Male":
        first = random.choice(_FIRST_NAMES_M)
    elif gender == "Female":
        first = random.choice(_FIRST_NAMES_F)
    else:
        first = random.choice(_FIRST_NAMES_NB)
    last = random.choice(_LAST_NAMES)
    return f"{first} {last}"


class CharacterCreator:
    """Factory for creating Character instances via interactive CLI, random
    generation, or predefined templates.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_interactive(self) -> Character:
        """Prompt the user step-by-step to build a character.

        Returns the fully constructed Character.
        """
        print("\n" + "═" * 50)
        print("  ✨  CHARACTER CREATION  ✨")
        print("═" * 50)

        # Name
        name = self._prompt("Enter character name", default=_random_name("Non-binary"))

        # Gender
        gender = self._prompt_choice("Choose gender", _GENDERS, default="Non-binary")

        # Race
        race_names = [r[0] for r in RACES]
        print("\n  Available races:")
        for i, (rname, rdesc, _) in enumerate(RACES, 1):
            print(f"  {i}. {rname:12s} — {rdesc[:60]}...")
        race = self._prompt_choice("Choose race", race_names, default=race_names[0])

        # Job
        job_names = [j[0] for j in JOBS]
        print("\n  Available jobs:")
        for i, (jname, jdesc, _) in enumerate(JOBS, 1):
            print(f"  {i}. {jname:12s} — {jdesc[:60]}...")
        job = self._prompt_choice("Choose job", job_names, default=job_names[0])

        # Age
        age_str = self._prompt("Enter starting age (15-80)", default="20")
        try:
            age = max(15, min(80, int(age_str)))
        except ValueError:
            age = 20

        # Stat allocation
        print("\n  You have 60 points to distribute among 6 stats (each 10–40).")
        print("  Press ENTER to accept the default (10 each).")
        stats = self._allocate_stats()

        # Apply race bonuses
        race_bonuses = next((r[2] for r in RACES if r[0] == race), {})
        for stat, bonus in race_bonuses.items():
            if stat in stats:
                stats[stat] = Character._clamp(stats[stat] + bonus)

        # Starting skills from job
        job_skills_raw = next((j[2] for j in JOBS if j[0] == job), [])
        skills = {s: 1 for s in job_skills_raw}

        char = Character(
            name=name, age=age, gender=gender, race=race, job=job,
            skills=skills, **stats,
        )
        char.add_history(f"Year 0: Born into the world as a {race} {job}.")
        print("\n  ✅  Character created!")
        print(char.stat_block())
        return char

    def create_random(self, name: Optional[str] = None) -> Character:
        """Generate a fully random character.

        Parameters
        ----------
        name
            If given, use this name; otherwise generate a random one.
        """
        gender = random.choice(_GENDERS)
        race_entry = random.choice(RACES)
        race = race_entry[0]
        race_bonuses = race_entry[2]

        job_entry = random.choice(JOBS)
        job = job_entry[0]
        job_skills = job_entry[2]

        age = random.randint(16, 55)
        char_name = name or _random_name(gender)

        stats = random_stats(base=25, spread=45, race_bonuses=race_bonuses)

        # 2-4 job skills at level 1-3, plus 1-2 random skills
        skills: Dict[str, int] = {}
        for s in job_skills:
            skills[s] = random.randint(1, 3)
        extra_skills = random.sample(ALL_SKILLS, k=min(2, len(ALL_SKILLS)))
        for s in extra_skills:
            if s not in skills:
                skills[s] = 1

        char = Character(
            name=char_name, age=age, gender=gender, race=race, job=job,
            skills=skills, **stats,
        )
        char.add_history(f"Year 0: Born into the world as a {race} {job}.")
        return char

    def create_from_template(self, template_name: str, name: Optional[str] = None) -> Character:
        """Create a character from a named preset.

        Available templates: warrior, mage, rogue, healer, merchant,
        paladin, druid.
        """
        key = template_name.lower().strip()
        if key not in _TEMPLATES:
            available = ", ".join(_TEMPLATES.keys())
            raise ValueError(f"Unknown template '{template_name}'. Available: {available}")

        tmpl = _TEMPLATES[key]
        race = tmpl["race"]
        job  = tmpl["job"]
        gender = random.choice(_GENDERS)
        char_name = name or _random_name(gender)
        age = random.randint(20, 40)

        # Add small random variation to base stats (±5)
        stats = {
            k: max(1, min(100, v + random.randint(-5, 5)))
            for k, v in tmpl["base_stats"].items()
        }

        skills = dict(tmpl["skills"])

        char = Character(
            name=char_name, age=age, gender=gender, race=race, job=job,
            skills=skills, **stats,
        )
        char.add_history(f"Year 0: Born into the world as a {race} {job}.")
        return char

    # ------------------------------------------------------------------
    # Interactive helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _prompt(message: str, default: str = "") -> str:
        """Display a prompt and return the user's input (or the default)."""
        display = f"  > {message}"
        if default:
            display += f" [{default}]"
        display += ": "
        raw = input(display).strip()
        return raw if raw else default

    @staticmethod
    def _prompt_choice(message: str, choices: List[str], default: str) -> str:
        """Prompt user to pick one item from *choices*."""
        display = f"  > {message} ({'/'.join(choices)}) [{default}]: "
        while True:
            raw = input(display).strip()
            if not raw:
                return default
            # Accept number
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(choices):
                    return choices[idx]
            # Accept partial name match (case-insensitive)
            matches = [c for c in choices if c.lower().startswith(raw.lower())]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                print(f"  Ambiguous — did you mean: {', '.join(matches)}?")
            else:
                print(f"  Invalid choice. Options: {', '.join(choices)}")

    @staticmethod
    def _allocate_stats() -> Dict[str, int]:
        """Let the user distribute 60 stat points, or skip for defaults."""
        stat_names = ["strength", "intelligence", "dexterity", "wisdom", "charisma", "constitution"]
        defaults = {s: 10 for s in stat_names}
        total_points = 60

        raw = input(f"  > Manually distribute stats? (y/N): ").strip().lower()
        if raw != "y":
            return defaults

        allocated: Dict[str, int] = {}
        remaining = total_points
        for i, stat in enumerate(stat_names):
            left = total_points - sum(allocated.values())
            remaining_stats = len(stat_names) - i
            min_needed = remaining_stats * 10
            max_allowed = min(40, left - (remaining_stats - 1) * 10)
            while True:
                raw_val = input(
                    f"  > {stat.capitalize():15s} (10-40, {left} pts left): "
                ).strip()
                if not raw_val:
                    val = 10
                else:
                    try:
                        val = int(raw_val)
                    except ValueError:
                        print("  Please enter a number.")
                        continue
                if val < 10 or val > max_allowed:
                    print(f"  Must be between 10 and {max_allowed}.")
                    continue
                if left - val < (remaining_stats - 1) * 10:
                    print(f"  Not enough points left for remaining stats. Max: {max_allowed}")
                    continue
                allocated[stat] = val
                break

        return allocated

    # ------------------------------------------------------------------
    # List available templates
    # ------------------------------------------------------------------

    @staticmethod
    def list_templates() -> List[str]:
        """Return a list of all available template names."""
        return list(_TEMPLATES.keys())
