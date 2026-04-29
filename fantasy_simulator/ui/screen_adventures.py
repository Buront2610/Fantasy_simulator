"""Adventure-related screen flows."""

from __future__ import annotations

from typing import Any

from ..i18n import tr, tr_term
from ..simulator import Simulator
from ..world import World
from .presenters import AdventurePresenter
from .screen_input import _get_numeric_choice
from .ui_context import UIContext, _default_ctx
from .view_models import AdventureSummaryView


def _party_display_names(world: World, run: Any, max_shown: int = 3) -> str:
    names = []
    for member_id in run.member_ids:
        character = world.get_character_by_id(member_id)
        if character is not None:
            names.append(character.name)
    if not names:
        names = [run.character_name]
    shown = names[:max_shown]
    label = " & ".join(shown)
    if len(names) > max_shown:
        label += f" +{len(names) - max_shown}"
    return label


def _show_adventure_summaries(sim: Simulator, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out

    runs = list(sim.world.completed_adventures) + list(sim.world.active_adventures)
    out.print_line()
    if not runs:
        out.print_dim(f"  {tr('no_adventures_recorded')}")
        ctx.inp.pause()
        return

    out.print_separator()
    out.print_heading(f"  {tr('adventure_summaries_header')}")
    out.print_separator()
    for i, run in enumerate(runs, 1):
        status = tr(f"outcome_{run.outcome}") if run.outcome else tr(f"state_{run.state}")
        origin_name = sim.world.location_name(run.origin)
        dest_name = sim.world.location_name(run.destination)
        if run.is_party:
            leader_display = _party_display_names(sim.world, run)
            policy_label = tr(f"policy_{run.policy}")
        else:
            leader_display = run.character_name
            policy_label = ""
        view = AdventureSummaryView(
            title=leader_display,
            status=status,
            origin=origin_name,
            destination=dest_name,
            policy=policy_label,
            loot=[tr_term(item) for item in run.loot_summary],
            injury=tr(f'injury_status_{run.injury_status}') if run.injury_status != "none" else "none",
        )
        out.print_line(AdventurePresenter.render_summary_row(i, view))
    out.print_separator()
    ctx.inp.pause()


def _show_adventure_details(sim: Simulator, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out

    runs = list(sim.world.completed_adventures) + list(sim.world.active_adventures)
    out.print_line()
    if not runs:
        out.print_dim(f"  {tr('no_adventures_to_inspect')}")
        ctx.inp.pause()
        return

    for i, run in enumerate(runs, 1):
        status = tr(f"outcome_{run.outcome}") if run.outcome else tr(f"state_{run.state}")
        dest_name = sim.world.location_name(run.destination)
        out.print_line(f"  {i:>2}. {run.character_name} {tr('at_label')} {dest_name} [{status}]")
    out.print_line()
    idx = _get_numeric_choice(f"  {tr('enter_adventure_number')}", len(runs), ctx=ctx)
    if idx is None:
        return

    run = runs[idx]
    out.print_line()
    out.print_separator()
    out.print_heading(f"  {tr('adventure_detail_header', name=run.character_name)}")
    out.print_separator()
    out.print_line(f"  {tr('id_label'):<11}: {run.adventure_id}")
    out.print_line(
        f"  {tr('route'):<11}: {sim.world.location_name(run.origin)} -> "
        f"{sim.world.location_name(run.destination)}"
    )
    if run.is_party:
        member_names = []
        for member_id in run.member_ids:
            character = sim.world.get_character_by_id(member_id)
            if character is not None:
                member_names.append(character.name)
        if not member_names:
            member_names = [run.character_name]
        out.print_line(f"  {tr('party_members_label'):<11}: {', '.join(member_names)}")
        out.print_line(f"  {tr('party_policy_label'):<11}: {tr(f'policy_{run.policy}')}")
        out.print_line(f"  {tr('party_supply_label'):<11}: {tr(f'supply_{run.supply_state}')}")
    out.print_line(f"  {tr('state'):<11}: {tr(f'state_{run.state}')}")
    out.print_line(
        f"  {tr('outcome'):<11}: {tr(f'outcome_{run.outcome}') if run.outcome else tr('unresolved')}"
    )
    out.print_line(f"  {tr('injury'):<11}: {tr(f'injury_status_{run.injury_status}')}")
    out.print_line(f"  {tr('steps'):<11}: {run.steps_taken}")
    if run.loot_summary:
        out.print_line(
            f"  {tr('discoveries'):<11}: {', '.join(tr_term(item) for item in run.loot_summary)}"
        )
    out.print_line()
    for entry in sim.get_adventure_details(run.adventure_id):
        out.print_line(f"  - {entry}")
    ctx.inp.pause()


def _resolve_pending_adventure_choice(sim: Simulator, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out

    pending = sim.get_pending_adventure_choices()
    out.print_line()
    if not pending:
        out.print_dim(f"  {tr('no_pending_choices')}")
        ctx.inp.pause()
        return

    for i, item in enumerate(pending, 1):
        options = ", ".join(tr(f"choice_{option}") for option in item["options"])
        default_label = tr(f"choice_{item['default_option']}")
        out.print_line(
            f"  {i:>2}. {item['character_name']} | {item['prompt']} "
            f"[{options}] {tr('choice_default_hint', default_option=default_label)}"
        )
    out.print_line()

    idx = _get_numeric_choice(f"  {tr('enter_pending_choice_number')}", len(pending), ctx=ctx)
    if idx is None:
        return

    item = pending[idx]
    options = item["options"]
    out.print_line()
    for i, option in enumerate(options, 1):
        default_marker = f" {tr('default_marker')}" if option == item["default_option"] else ""
        out.print_line(f"  {i:>2}. {tr(f'choice_{option}')}{default_marker}")
    option_idx = _get_numeric_choice(f"  {tr('enter_option_number')}", len(options), ctx=ctx)
    chosen_option = options[option_idx] if option_idx is not None else None

    resolved = sim.resolve_adventure_choice(item["adventure_id"], option=chosen_option)
    out.print_line()
    if resolved:
        out.print_success(f"  {tr('choice_resolved')}")
    else:
        out.print_error(f"  {tr('choice_resolve_failed')}")
    ctx.inp.pause()
