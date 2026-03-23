"""
world_data.py - Predefined lore, races, jobs, locations, and skills for the fantasy world.
"""

from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# World lore
# ---------------------------------------------------------------------------

WORLD_LORE: str = """
Welcome to AETHORIA — a continent shaped by ancient magic and forgotten wars.

Long ago, the Arcane Cataclysm tore the sky open for seven days and seven nights,
leaving behind ley-lines of wild mana that pulse through mountain, forest, and sea.
The Great Kingdoms rose and fell atop these ley-lines, and the scars of those
civilizations are still visible in crumbling ruins and cursed dungeons scattered
across the land.

Today, an uneasy peace holds among the city-states. Adventurers roam freely,
seeking fortune and glory — or simply trying to survive in a world where the next
monster, war, or natural disaster is never far away.

The current era is called the Age of Embers: old powers are fading, new ones are
rising, and destiny waits for those bold enough to seize it.
"""

# ---------------------------------------------------------------------------
# Races: (name, description, stat_bonuses)
# ---------------------------------------------------------------------------

RACES: List[Tuple[str, str, Dict[str, int]]] = [
    (
        "Human",
        "Adaptable and ambitious. Humans are found everywhere and excel at nothing — "
        "except perseverance.",
        {"strength": 0, "intelligence": 0, "dexterity": 0,
         "wisdom": 0, "charisma": 5, "constitution": 0},
    ),
    (
        "Elf",
        "Long-lived and graceful. Elves carry centuries of wisdom in their eyes and "
        "a quiet sadness in their hearts.",
        {"strength": -2, "intelligence": 8, "dexterity": 6,
         "wisdom": 5, "charisma": 3, "constitution": -3},
    ),
    (
        "Dwarf",
        "Stout and stubborn. Dwarves are master craftsmen who remember every grudge "
        "ever dealt to their kin.",
        {"strength": 6, "intelligence": 0, "dexterity": -3,
         "wisdom": 3, "charisma": -2, "constitution": 10},
    ),
    (
        "Halfling",
        "Small but surprisingly resilient. Halflings have an almost supernatural "
        "talent for finding comfort in chaos.",
        {"strength": -5, "intelligence": 2, "dexterity": 8,
         "wisdom": 2, "charisma": 6, "constitution": 0},
    ),
    (
        "Orc",
        "Fierce warriors shaped by harsh lands. Orcs value strength and loyalty "
        "above all else.",
        {"strength": 12, "intelligence": -4, "dexterity": 0,
         "wisdom": -2, "charisma": -3, "constitution": 8},
    ),
    (
        "Tiefling",
        "Touched by infernal blood. Tieflings carry a stigma they did not choose "
        "and often forge their own path despite it.",
        {"strength": 0, "intelligence": 5, "dexterity": 3,
         "wisdom": 0, "charisma": 7, "constitution": 0},
    ),
    (
        "Dragonborn",
        "Descendants of dragons. Proud and powerful, they carry a primal fire within.",
        {"strength": 8, "intelligence": 2, "dexterity": 0,
         "wisdom": 0, "charisma": 4, "constitution": 6},
    ),
]

# ---------------------------------------------------------------------------
# Jobs: (name, description, primary_skills)
# ---------------------------------------------------------------------------

JOBS: List[Tuple[str, str, List[str]]] = [
    (
        "Warrior",
        "Masters of the blade and shield, warriors charge headlong into battle and "
        "endure what others cannot.",
        ["Swordsmanship", "Shield Block", "Battle Cry", "Endurance"],
    ),
    (
        "Mage",
        "Scholars of the arcane arts, mages wield reality-bending spells with "
        "intellect and force of will.",
        ["Fireball", "Arcane Shield", "Mana Control", "Spellcraft"],
    ),
    (
        "Rogue",
        "Shadows in the night. Rogues survive on wit, speed, and a healthy "
        "disrespect for authority.",
        ["Stealth", "Backstab", "Lockpicking", "Evasion"],
    ),
    (
        "Healer",
        "Channelers of divine or natural energy. Healers sustain their companions "
        "and mend wounds that would fell lesser folk.",
        ["Holy Light", "Regeneration", "Purify", "Blessing"],
    ),
    (
        "Ranger",
        "Children of the wild. Rangers read the land like a book and strike from "
        "distances their enemies can't match.",
        ["Archery", "Track", "Animal Bond", "Camouflage"],
    ),
    (
        "Merchant",
        "The lifeblood of civilisation. Merchants turn profit from chaos and know "
        "the value of everything — and the price of everyone.",
        ["Appraisal", "Bargaining", "Trade Routes", "Persuasion"],
    ),
    (
        "Paladin",
        "Holy warriors bound by oath. Paladins blend divine magic with martial "
        "skill in service of a higher calling.",
        ["Holy Strike", "Divine Shield", "Lay on Hands", "Aura of Courage"],
    ),
    (
        "Bard",
        "Wandering storytellers and musicians. Bards inspire allies, bewilder "
        "enemies, and always have a song for the occasion.",
        ["Inspire", "Charm Song", "Lore Mastery", "Quick Wit"],
    ),
    (
        "Druid",
        "Guardians of nature's balance. Druids command the elements and commune "
        "with beasts and spirits.",
        ["Nature's Wrath", "Wild Shape", "Commune", "Entangle"],
    ),
    (
        "Alchemist",
        "Half-scientist, half-wizard. Alchemists brew potions and explosive "
        "concoctions that blur the line between art and danger.",
        ["Brew Potion", "Transmute", "Elemental Analysis", "Explosive Flask"],
    ),
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
    # Row 0 (north)
    ("loc_frostpeak_summit", "Frostpeak Summit",
     "A jagged mountain crowned with eternal ice.", "mountain", 0, 0),
    ("loc_the_grey_pass", "The Grey Pass",
     "A treacherous alpine pass haunted by wind spirits.", "mountain", 1, 0),
    ("loc_skyveil_monastery", "Skyveil Monastery",
     "A cliffside monastery where monks study the ley-lines.", "village", 2, 0),
    ("loc_ironvein_mine", "Ironvein Mine",
     "A deep mine rich in enchanted ore — and old curses.", "dungeon", 3, 0),
    ("loc_stormwatch_keep", "Stormwatch Keep",
     "A fortress overlooking the northern sea.", "mountain", 4, 0),

    # Row 1
    ("loc_thornwood", "Thornwood",
     "A dense forest that hums with restless magic.", "forest", 0, 1),
    ("loc_ashenvale", "Ashenvale",
     "Charred woodland recovering from a decade-old wildfire.", "forest", 1, 1),
    ("loc_silverbrook", "Silverbrook",
     "A prosperous trading town built on a swift silver river.", "city", 2, 1),
    ("loc_goblin_warrens", "Goblin Warrens",
     "A network of tunnels teeming with mischievous creatures.", "dungeon", 3, 1),
    ("loc_eastwatch_tower", "Eastwatch Tower",
     "A lone watchtower staffed by a rotating ranger garrison.", "village", 4, 1),

    # Row 2 (middle)
    ("loc_elderroot_forest", "Elderroot Forest",
     "An ancient forest whose trees remember the Cataclysm.", "forest", 0, 2),
    ("loc_millhaven", "Millhaven",
     "A quiet farming village known for its legendary apple wine.", "village", 1, 2),
    ("loc_aethoria_capital", "Aethoria Capital",
     "The grand capital — heart of trade, politics, and intrigue.", "city", 2, 2),
    ("loc_sunken_ruins", "Sunken Ruins",
     "Ruins of a pre-Cataclysm city, half-swallowed by the earth.", "dungeon", 3, 2),
    ("loc_saltmarsh", "Saltmarsh",
     "A fishing village where sailors whisper of sea monsters.", "village", 4, 2),

    # Row 3
    ("loc_dragonbone_ridge", "Dragonbone Ridge",
     "A ridge littered with the bones of ancient dragons.", "mountain", 0, 3),
    ("loc_dusty_crossroads", "Dusty Crossroads",
     "A well-worn junction where merchants rest and rumours spread.", "plains", 1, 3),
    ("loc_hearthglow_town", "Hearthglow Town",
     "A warm, welcoming town renowned for its healers' guild.", "city", 2, 3),
    ("loc_mirefen_swamp", "Mirefen Swamp",
     "A murky swamp hiding both treasure and terrible dangers.", "dungeon", 3, 3),
    ("loc_dawnport", "Dawnport",
     "A busy harbour city that never truly sleeps.", "city", 4, 3),

    # Row 4 (south)
    ("loc_sunbaked_plains", "Sunbaked Plains",
     "Vast golden plains scorched by an unrelenting sun.", "plains", 0, 4),
    ("loc_sandstone_outpost", "Sandstone Outpost",
     "A small desert outpost at the edge of the known world.", "village", 1, 4),
    ("loc_the_verdant_vale", "The Verdant Vale",
     "A lush valley sheltered from harsh winds — a true paradise.", "village", 2, 4),
    ("loc_obsidian_crater", "Obsidian Crater",
     "A massive crater from the Cataclysm, still faintly glowing.", "dungeon", 3, 4),
    ("loc_coral_cove", "Coral Cove",
     "A hidden cove home to a secretive community of sea-mages.", "city", 4, 4),
]

NAME_TO_LOCATION_ID: Dict[str, str] = {entry[1]: entry[0] for entry in DEFAULT_LOCATIONS}


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

CAPITAL_LOCATION_IDS = {"loc_aethoria_capital"}


def fallback_location_id(name: str) -> str:
    """Generate a location ID from a name when no canonical mapping exists."""
    slug = name.lower().replace(' ', '_').replace('-', '_').replace("'", '')
    return f"loc_{slug}"


def get_location_state_defaults(loc_id: str, region_type: str) -> Dict[str, int]:
    """Return initial state values for a location."""
    profile = "capital" if loc_id in CAPITAL_LOCATION_IDS else region_type
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
