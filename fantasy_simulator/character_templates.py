"""Built-in character template compatibility helpers."""

from __future__ import annotations

from typing import Iterable, List, Tuple

from .character_creator_template_data import TEMPLATES

TEMPLATE_REQUIRED_IDENTITIES = {
    (template["race"], template["job"])
    for template in TEMPLATES.values()
}


def supported_template_names(
    *,
    world_key: str,
    has_explicit_race_or_job_data: bool,
    race_names: Iterable[str],
    job_names: Iterable[str],
    using_default_bundle: bool,
) -> List[str]:
    """Return built-in template names supported by a creator context."""
    if using_default_bundle:
        return list(TEMPLATES.keys())
    if world_key != "aethoria":
        return []
    if not has_explicit_race_or_job_data:
        return list(TEMPLATES.keys())
    races = set(race_names)
    jobs = set(job_names)
    if all(race in races and job in jobs for race, job in TEMPLATE_REQUIRED_IDENTITIES):
        return list(TEMPLATES.keys())
    return []


def template_identity_pairs() -> set[Tuple[str, str]]:
    """Return race/job pairs required by all built-in templates."""
    return set(TEMPLATE_REQUIRED_IDENTITIES)
