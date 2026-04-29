"""Character roster screen flow."""

from __future__ import annotations

from ..i18n import tr, tr_term
from ..world import World
from .ui_context import UIContext, _default_ctx
from .ui_helpers import fit_display_width


def _show_roster(world: World, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out

    out.print_line()
    out.print_separator()
    header = (
        "  "
        + fit_display_width(tr("roster_header_name"), 22)
        + " "
        + fit_display_width(tr("roster_header_race_job"), 22)
        + " "
        + fit_display_width(tr("roster_header_age"), 4)
        + "  "
        + fit_display_width(tr("stat_str"), 4)
        + fit_display_width(tr("stat_int"), 4)
        + fit_display_width(tr("stat_dex"), 4)
        + "  "
        + fit_display_width(tr("roster_header_status"), 10)
        + "  "
        + fit_display_width(tr("roster_header_location"), 20)
    )
    out.print_heading(header)
    out.print_separator()
    for c in world.characters:
        status_text = fit_display_width(
            tr("status_alive") if c.alive else tr("status_dead"),
            10,
        )
        status = out.format_status(status_text, c.alive)
        name_trunc = fit_display_width(c.name, 22)
        racejob = fit_display_width(f"{tr_term(c.race)} {tr_term(c.job)}", 22)
        loc_trunc = fit_display_width(world.location_name(c.location_id), 20)
        out.print_line(
            f"  {name_trunc} {racejob} {c.age:>4}  "
            f"{c.strength:>4}{c.intelligence:>4}{c.dexterity:>4}  "
            f"{status}  {loc_trunc}"
        )
    out.print_separator()
    ctx.inp.pause()
