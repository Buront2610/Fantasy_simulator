"""Aethoria compatibility projections for bundled world-setting data plus legacy flavor tables.

The module-level globals here are import-time snapshots of the bundled default
Aethoria setting. New bundle-aware code should prefer ``SettingBundle`` data
from the active world instead of importing these globals directly.
"""

from typing import Dict, List, Tuple

from .setting_bundle import default_aethoria_bundle, legacy_location_id_alias


_DEFAULT_AETHORIA_BUNDLE = default_aethoria_bundle()
_WORLD_DEFINITION = _DEFAULT_AETHORIA_BUNDLE.world_definition


# ---------------------------------------------------------------------------
# Bundle-backed compatibility projections
# ---------------------------------------------------------------------------

WORLD_LORE: str = _WORLD_DEFINITION.lore_text

RACES: List[Tuple[str, str, Dict[str, int]]] = [
    (race.name, race.description, dict(race.stat_bonuses))
    for race in _WORLD_DEFINITION.races
]

JOBS: List[Tuple[str, str, List[str]]] = [
    (job.name, job.description, list(job.primary_skills))
    for job in _WORLD_DEFINITION.jobs
]

# ---------------------------------------------------------------------------
# Skills by category
# ---------------------------------------------------------------------------

SKILLS: Dict[str, List[str]] = {
    "Combat": [
        "Swordsmanship", "Archery", "Shield Block", "Unarmed Combat",
        "Dual Wield", "Battle Cry", "Heavy Armor", "Light Armor",
    ],
    "Magic": [
        "Fireball", "Arcane Shield", "Mana Control", "Spellcraft",
        "Holy Light", "Regeneration", "Nature's Wrath", "Illusion",
        "Necromancy", "Elemental Magic", "Entangle",
    ],
    "Stealth": [
        "Stealth", "Backstab", "Lockpicking", "Pickpocket", "Camouflage",
        "Evasion", "Trap Disarm",
    ],
    "Social": [
        "Persuasion", "Charm Song", "Intimidation", "Bargaining",
        "Inspire", "Quick Wit", "Lore Mastery",
    ],
    "Survival": [
        "Track", "Animal Bond", "Foraging", "Endurance", "Navigation",
        "First Aid", "Climbing",
    ],
    "Crafting": [
        "Brew Potion", "Blacksmithing", "Alchemy", "Enchanting",
        "Transmute", "Appraisal", "Trade Routes",
    ],
    "Divine": [
        "Holy Strike", "Divine Shield", "Lay on Hands", "Purify",
        "Blessing", "Aura of Courage", "Commune",
    ],
    "Exploration": [
        "Dungeoneering", "Cartography", "Arcane Sensing",
        "Explosive Flask", "Elemental Analysis", "Wild Shape",
    ],
}

ALL_SKILLS: List[str] = [s for skills in SKILLS.values() for s in skills]

# ---------------------------------------------------------------------------
# Locations for the default 5×5 world map
# Each entry: (id, name, description, region_type, grid_x, grid_y)
# region_type: city | village | forest | dungeon | mountain | plains | sea
# ---------------------------------------------------------------------------

DEFAULT_LOCATIONS = [
    seed.as_world_data_entry()
    for seed in _WORLD_DEFINITION.site_seeds
]

NAME_TO_LOCATION_ID: Dict[str, str] = {entry[1]: entry[0] for entry in DEFAULT_LOCATIONS}
_SITE_SEED_TAGS_BY_ID: Dict[str, List[str]] = {
    seed.location_id: list(seed.tags)
    for seed in _WORLD_DEFINITION.site_seeds
}


LOCATION_STATE_DEFAULTS: Dict[str, Dict[str, int]] = {
    "capital": {
        "prosperity": 85,
        "safety": 80,
        "mood": 65,
        "danger": 15,
        "traffic": 90,
        "rumor_heat": 60,
        "road_condition": 85,
    },
    "city": {
        "prosperity": 70,
        "safety": 65,
        "mood": 55,
        "danger": 25,
        "traffic": 70,
        "rumor_heat": 45,
        "road_condition": 75,
    },
    "village": {
        "prosperity": 50,
        "safety": 55,
        "mood": 55,
        "danger": 30,
        "traffic": 35,
        "rumor_heat": 20,
        "road_condition": 55,
    },
    "forest": {
        "prosperity": 10,
        "safety": 30,
        "mood": 40,
        "danger": 55,
        "traffic": 15,
        "rumor_heat": 10,
        "road_condition": 35,
    },
    "mountain": {
        "prosperity": 5,
        "safety": 25,
        "mood": 35,
        "danger": 65,
        "traffic": 10,
        "rumor_heat": 10,
        "road_condition": 30,
    },
    "dungeon": {
        "prosperity": 0,
        "safety": 10,
        "mood": 20,
        "danger": 80,
        "traffic": 5,
        "rumor_heat": 35,
        "road_condition": 20,
    },
    "plains": {
        "prosperity": 35,
        "safety": 45,
        "mood": 50,
        "danger": 35,
        "traffic": 30,
        "rumor_heat": 15,
        "road_condition": 60,
    },
    "sea": {
        "prosperity": 0,
        "safety": 20,
        "mood": 40,
        "danger": 60,
        "traffic": 25,
        "rumor_heat": 20,
        "road_condition": 0,
    },
}

CAPITAL_LOCATION_IDS = {
    seed.location_id
    for seed in _WORLD_DEFINITION.site_seeds
    if seed.has_tag("capital")
}


def fallback_location_id(name: str) -> str:
    """Generate a location ID from a name when no canonical mapping exists."""
    return legacy_location_id_alias(name)


def get_location_state_defaults(
    loc_id: str,
    region_type: str,
    site_tags: List[str] | None = None,
) -> Dict[str, int]:
    """Return initial state values for a location."""
    effective_tags = site_tags if site_tags is not None else _SITE_SEED_TAGS_BY_ID.get(loc_id, [])
    profile = "capital" if "capital" in effective_tags or loc_id in CAPITAL_LOCATION_IDS else region_type
    defaults = LOCATION_STATE_DEFAULTS.get(profile, LOCATION_STATE_DEFAULTS["city"])
    return dict(defaults)


# ---------------------------------------------------------------------------
# Event flavour fragments used by events.py
# ---------------------------------------------------------------------------

DISCOVERY_ITEMS = [
    "an ancient map covered in unknown runes",
    "a crystallised dragon tear worth a small fortune",
    "a sealed tome bound in shadow-leather",
    "a vein of star-metal ore",
    "a hidden shrine to a forgotten deity",
    "a cache of pre-Cataclysm gold coins",
    "a fragment of a prophetic tablet",
    "a living plant that glows in the dark",
    "a mysterious portal to an unknown realm",
    "a weapon of legendary make, lost for centuries",
]

BATTLE_OUTCOMES_WIN = [
    "landed a decisive blow",
    "outmaneuvered their opponent",
    "unleashed a devastating skill",
    "held firm and wore down the enemy",
    "turned the tide with a surprise tactic",
]

BATTLE_OUTCOMES_LOSE = [
    "was overwhelmed",
    "misjudged the enemy's strength",
    "ran out of stamina",
    "was caught off-guard",
    "underestimated the danger",
]

JOURNEY_EVENTS = [
    "encountered bandits on the road but bluffed their way past",
    "helped a lost child find their village",
    "stumbled upon a travelling circus and spent the night",
    "survived a sudden storm in the open wild",
    "traded stories with a wandering bard",
    "discovered a shortcut through the hills",
    "was briefly chased by a hungry wolf pack",
    "witnessed a breathtaking meteor shower",
]
