"""Save/load screen helpers."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any, Optional

from ..i18n import tr
from .ui_context import UIContext, _default_ctx


def _confirm_overwrite(path: str, ctx: UIContext) -> bool:
    choice = ctx.choose_key(
        tr("save_overwrite_prompt", path=path),
        [
            ("overwrite", tr("save_overwrite_confirm")),
            ("cancel", tr("save_overwrite_cancel")),
        ],
        default="2",
    )
    return choice == "overwrite"


def _save_simulation_snapshot(sim: Any, ctx: UIContext | None = None) -> bool:
    ctx = _default_ctx(ctx)
    out = ctx.out

    out.print_line()
    default_name = "simulation_snapshot.json"
    path = ctx.inp.read_line(f"  {tr('save_path_prompt', default_name=default_name)}").strip() or default_name
    if Path(path).exists() and not _confirm_overwrite(path, ctx):
        out.print_warning(f"  {tr('save_cancelled')}")
        ctx.inp.pause()
        return False

    save_simulation = import_module("fantasy_simulator.persistence.save_load").save_simulation
    if save_simulation(sim, path):
        out.print_success(f"  {tr('save_succeeded', path=path)}")
        ctx.inp.pause()
        return True
    else:
        out.print_error(f"  {tr('save_failed', error=tr('save_error_io'))}")
    ctx.inp.pause()
    return False


def _load_simulation_snapshot(ctx: UIContext | None = None) -> Optional[Any]:
    ctx = _default_ctx(ctx)
    out = ctx.out

    out.print_line()
    out.print_separator("=")
    out.print_heading(f"  {tr('load_snapshot_header')}")
    out.print_separator("=")
    default_name = "simulation_snapshot.json"
    path = ctx.inp.read_line(f"  {tr('load_path_prompt', default_name=default_name)}").strip() or default_name
    load_simulation = import_module("fantasy_simulator.persistence.save_load").load_simulation
    sim = load_simulation(path)
    if sim is None:
        out.print_error(f"  {tr('load_failed', error=tr('load_error_corrupted'))}")
        ctx.inp.pause()
        return None

    out.print_success(f"  {tr('load_succeeded', path=path)}")
    return sim
