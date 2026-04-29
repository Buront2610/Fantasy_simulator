"""Top-level simulation setup screen flows."""

from __future__ import annotations

from typing import List

from ..character import Character
from ..character_creator import CharacterCreator
from ..i18n import tr, tr_term
from ..world import World
from .screen_input import _read_bounded_int
from .screen_results import _show_results
from .screen_simulation import _build_default_world, _run_simulation
from .ui_context import UIContext, _default_ctx


def screen_new_simulation(ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out

    out.print_line()
    out.print_separator("=")
    out.print_heading(f"  {tr('new_simulation')} - {tr('default_world')}")
    out.print_separator("=")

    num = _read_bounded_int(
        f"  > {tr('number_of_characters')}: ",
        default=12,
        minimum=4,
        maximum=30,
        ctx=ctx,
    )
    years = _read_bounded_int(
        f"  > {tr('simulation_length')}: ",
        default=20,
        minimum=1,
        maximum=200,
        ctx=ctx,
    )

    world = _build_default_world(num_characters=num)
    out.print_line()
    out.print_success(f"  {tr('world_created', world=world.name, count=num)}")
    sim = _run_simulation(world, years, ctx=ctx)
    _show_results(sim, ctx=ctx)


def screen_custom_simulation(ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out
    inp = ctx.inp

    out.print_line()
    out.print_separator("=")
    out.print_heading(f"  {tr('custom_character_simulation')}")
    out.print_separator("=")
    creator = CharacterCreator()
    world = World()
    custom_chars: List[Character] = []

    while True:
        action = ctx.choose_key(
            tr("add_character_or_start"),
            [
                ("create_interactive", tr("create_character_interactively")),
                ("create_random", tr("create_random_character")),
                ("create_template", tr("create_from_template")),
                ("start_simulation", tr("start_simulation_with_roster", count=len(custom_chars))),
            ],
        )

        if action == "create_interactive":
            char = creator.create_interactive(ctx=ctx)
            world.add_character(char)
            custom_chars.append(char)
            out.print_line()
            out.print_success(f"  {tr('character_added', name=char.name)}")
        elif action == "create_random":
            char = creator.create_random()
            world.add_character(char)
            custom_chars.append(char)
            msg = tr("random_character_added", name=char.name, race=tr_term(char.race), job=tr_term(char.job))
            out.print_line()
            out.print_success(f"  {msg}")
        elif action == "create_template":
            templates = creator.list_templates()
            if not templates:
                out.print_warning(f"  {tr('no_templates_available')}")
                continue
            out.print_line(f"\n  {tr('available_templates')}: " + ", ".join(templates))
            tmpl_name = inp.read_line(f"  > {tr('template_name')}: ").strip()
            char_name = inp.read_line(f"  > {tr('character_name_optional')}: ").strip() or None
            try:
                char = creator.create_from_template(tmpl_name, name=char_name)
                world.add_character(char)
                custom_chars.append(char)
                out.print_line()
                msg = tr(
                    "template_character_added",
                    name=char.name,
                    race=tr_term(char.race),
                    job=tr_term(char.job),
                )
                out.print_success(f"  {msg}")
            except ValueError as exc:
                out.print_error(f"  {tr('error_prefix')}: {exc}")
        else:
            if not custom_chars:
                out.print_warning(f"  {tr('need_one_character')}")
                for _ in range(5):
                    world.add_character(creator.create_random())

            fill = max(0, 8 - len(world.characters))
            for _ in range(fill):
                world.add_character(creator.create_random())

            years = _read_bounded_int(
                f"  > {tr('simulation_length')}: ",
                default=20,
                minimum=1,
                maximum=200,
                ctx=ctx,
            )

            sim = _run_simulation(world, years, ctx=ctx)
            _show_results(sim, ctx=ctx)
            break
