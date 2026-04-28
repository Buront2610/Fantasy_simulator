"""Character display helpers and stat rolling."""

from __future__ import annotations

import random
from typing import Any, Callable, Dict, Optional

from .i18n import tr, tr_term


def character_stat_block(
    character: Any,
    *,
    char_name_lookup: Optional[Dict[str, str]] = None,
    location_resolver: Callable[[str], str] | None = None,
) -> str:
    location_name = character.location_display_name
    if location_resolver is not None and character.location_id:
        location_name = location_resolver(character.location_id)
    lines = [
        f"  {tr('name_label'):<10}: {character.name}",
        f"  {tr('race_job_label'):<10}: {tr_term(character.race)} {tr_term(character.job)}",
        f"  {tr('age_gender_label'):<10}: {character.age}  |  {tr('gender_label')}: {tr_term(character.gender)}",
        f"  {tr('location_label'):<10}: {location_name}",
        f"  {tr('status_label'):<10}: {tr('status_alive') if character.alive else tr('status_dead')}",
        f"  {tr('stats_label')}",
        (
            f"  {tr('stat_str')} {character.strength:>3}  |  "
            f"{tr('stat_int')} {character.intelligence:>3}  |  "
            f"{tr('stat_dex')} {character.dexterity:>3}"
        ),
        (
            f"  {tr('stat_wis')} {character.wisdom:>3}  |  "
            f"{tr('stat_cha')} {character.charisma:>3}  |  "
            f"{tr('stat_con')} {character.constitution:>3}"
        ),
    ]
    if character.skills:
        top_skills = sorted(character.skills.items(), key=lambda x: -x[1])[:5]
        skill_str = "  |  ".join(f"{tr_term(k)}(Lv{v})" for k, v in top_skills)
        lines.append(f"  {tr('top_skills_label')}")
        lines.append(f"  {skill_str}")
    if character.injury_status != "none":
        lines.append(f"  {tr('injury_label'):<10}: {tr(f'injury_status_{character.injury_status}')}")
    if character.relation_tags:
        lines.append(f"  {tr('relations_label')}")
        for other_id, tags in list(character.relation_tags.items())[:5]:
            tag_str = ", ".join(tr(f"relation_tag_{t}") for t in tags)
            display_name = other_id[:8]
            if char_name_lookup is not None:
                display_name = char_name_lookup.get(other_id, display_name)
            lines.append(f"    {display_name}: {tag_str}")
    return "\n".join(lines)


def random_stats(
    base: int = 30,
    spread: int = 40,
    race_bonuses: Optional[Dict[str, int]] = None,
    rng: Any = random,
) -> Dict[str, int]:
    bonuses = race_bonuses or {}
    result: Dict[str, int] = {}
    for stat in ("strength", "intelligence", "dexterity", "wisdom", "charisma", "constitution"):
        raw = rng.randint(base, base + spread) + bonuses.get(stat, 0)
        result[stat] = max(1, min(100, raw))
    return result
