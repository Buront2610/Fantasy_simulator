"""Built-in Aethoria character template data."""

from __future__ import annotations

from typing import Dict


TEMPLATES: Dict[str, Dict] = {
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
