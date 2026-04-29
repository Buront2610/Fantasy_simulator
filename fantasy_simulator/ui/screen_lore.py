"""World lore screen flow."""

from __future__ import annotations

from typing import Any, List

from ..character_creator import CharacterCreator
from ..content.setting_bundle import default_aethoria_bundle
from ..i18n import tr, tr_term
from ..world import World
from .presenters import LanguagePresenter
from .ui_context import UIContext, _default_ctx


def screen_world_lore(ctx: UIContext | None = None, *, world: World | None = None) -> None:
    """Show lore using the active world's bundle, or the default bundle pre-sim."""

    ctx = _default_ctx(ctx)
    out = ctx.out
    bundle = world.setting_bundle if world is not None else default_aethoria_bundle()
    world_definition = bundle.world_definition
    creator = CharacterCreator(setting_bundle=bundle)
    lore_text = world_definition.lore_text

    out.print_line()
    out.print_separator("=")
    out.print_heading(f"  {tr('world_lore')}")
    out.print_separator("=")
    out.print_wrapped(lore_text)
    out.print_line()
    out.print_heading(f"  {tr('races_of_aethoria')}")
    out.print_separator()
    for race_name, race_description, stat_bonuses in creator.race_entries:
        bonus_str = ", ".join(
            f"{stat} {'+' if value >= 0 else ''}{value}"
            for stat, value in stat_bonuses.items()
            if value != 0
        )
        out.print_highlighted(f"  {tr_term(race_name)}")
        out.print_wrapped(race_description)
        if bonus_str:
            out.print_dim(f"    {tr('bonuses')}: {bonus_str}")
        out.print_line()
    out.print_heading(f"  {tr('jobs_classes')}")
    out.print_separator()
    for job_name, job_description, primary_skills in creator.job_entries:
        skills_str = ", ".join(tr_term(skill) for skill in primary_skills)
        out.print_highlighted(f"  {tr_term(job_name)}")
        out.print_line(f"    {tr('primary_skills_label')}: {skills_str}")
        out.print_wrapped(job_description)
        out.print_line()
    language_statuses = world.language_status() if world is not None else _build_default_language_status(bundle)
    if language_statuses:
        out.print_heading(f"  {tr('languages_header')}")
        out.print_separator()
        for status in language_statuses:
            for line in LanguagePresenter.render_status(status):
                out.print_line(line)
            out.print_line()
    ctx.inp.pause()


def _build_default_language_status(bundle: Any) -> List[dict]:
    """Build language status for bundle lore without requiring a simulated world."""
    from ..language.engine import LanguageEngine
    from ..world_language import language_status

    engine = LanguageEngine(bundle.world_definition)
    return language_status(bundle.world_definition, engine, [])
