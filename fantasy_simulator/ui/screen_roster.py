"""Character roster screen flow."""

from __future__ import annotations

from typing import Any

from ..character_founder_background import render_founder_summary
from ..character_personality import render_personality_summary
from ..combat_log_index import CombatLogEntryView, build_combat_log_index
from ..i18n import tr, tr_term
from ..world import World
from .screen_input import _get_numeric_choice
from .ui_context import UIContext, _default_ctx
from .ui_helpers import fit_display_width


RECENT_HISTORY_LIMIT = 8
PROFILE_RELATION_LIMIT = 6
PROFILE_COMBAT_LIMIT = 5


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
    choice = _get_numeric_choice(f"  {tr('roster_detail_prompt')}", len(world.characters), ctx=ctx)
    if choice is None:
        return
    _show_character_profile(world, world.characters[choice], ctx)


def _show_character_profile(world: World, character: Any, ctx: UIContext) -> None:
    ctx.out.print_line()
    ctx.out.print_heading(f"  {tr('roster_profile_header', name=character.name)}")
    for line in _profile_summary_lines(world, character):
        ctx.out.print_line(f"  {line}")
    _print_profile_section(ctx, tr("roster_profile_background"), _background_lines(character))
    _print_profile_section(ctx, tr("roster_profile_family"), _family_lines(world, character))
    _print_profile_section(ctx, tr("roster_profile_relationships"), _relationship_lines(world, character))
    _print_profile_section(ctx, tr("roster_profile_recent_history"), _history_lines(character))
    _print_profile_section(ctx, tr("roster_profile_recent_combat"), _combat_lines(world, character))
    ctx.inp.pause()


def _profile_summary_lines(world: World, character: Any) -> list[str]:
    status = tr("status_alive") if getattr(character, "alive", True) else tr("status_dead")
    injury = tr(f"injury_status_{getattr(character, 'injury_status', 'none')}")
    return [
        tr(
            "roster_profile_identity",
            race=tr_term(getattr(character, "race", "")),
            job=tr_term(getattr(character, "job", "")),
            age=getattr(character, "age", 0),
            status=status,
            injury=injury,
            location=world.location_name(getattr(character, "location_id", "")),
        ),
        tr(
            "roster_profile_stats",
            strength=getattr(character, "strength", 0),
            intelligence=getattr(character, "intelligence", 0),
            dexterity=getattr(character, "dexterity", 0),
            wisdom=getattr(character, "wisdom", 0),
            charisma=getattr(character, "charisma", 0),
            constitution=getattr(character, "constitution", 0),
        ),
        tr("roster_profile_personality", summary=render_personality_summary(character.personality)),
    ]


def _background_lines(character: Any) -> list[str]:
    background = getattr(character, "founder_background", None)
    if not isinstance(background, dict):
        return [tr("roster_profile_no_background")]
    return [render_founder_summary(background)]


def _family_lines(world: World, character: Any) -> list[str]:
    lines: list[str] = []
    spouse_id = getattr(character, "spouse_id", None)
    spouse = world.get_character_by_id(spouse_id) if isinstance(spouse_id, str) and spouse_id else None
    if spouse is not None:
        lines.append(tr("roster_profile_spouse", name=spouse.name))
    parents = _related_characters(world, character, "parent")
    children = _related_characters(world, character, "child")
    if parents:
        lines.append(tr("roster_profile_parents", names=", ".join(parent.name for parent in parents)))
    if children:
        lines.append(tr("roster_profile_children", names=", ".join(child.name for child in children)))
    return lines or [tr("roster_profile_no_family")]


def _relationship_lines(world: World, character: Any) -> list[str]:
    relationship_details = getattr(character, "relationship_details", {})
    rows: list[tuple[int, str]] = []
    for target_id, relation in relationship_details.items():
        target = world.get_character_by_id(target_id)
        if target is None:
            continue
        tags = [
            _relation_tag_label(tag)
            for tag in getattr(relation, "tags", ())
        ]
        tag_text = f" [{', '.join(tags)}]" if tags else ""
        score = int(getattr(relation, "score", 0) or 0)
        rows.append((abs(score), tr("roster_profile_relation", name=target.name, score=score, tags=tag_text)))
    rows.sort(key=lambda item: item[0], reverse=True)
    return [line for _, line in rows[:PROFILE_RELATION_LIMIT]] or [tr("roster_profile_no_relationships")]


def _history_lines(character: Any) -> list[str]:
    history = [str(entry) for entry in getattr(character, "history", []) if str(entry).strip()]
    return history[-RECENT_HISTORY_LIMIT:] or [tr("roster_profile_no_history")]


def _combat_lines(world: World, character: Any) -> list[str]:
    entries = build_combat_log_index(world, character_id=getattr(character, "char_id", ""))[:PROFILE_COMBAT_LIMIT]
    return [_combat_entry_line(world, entry) for entry in entries] or [tr("combat_logs_empty")]


def _combat_entry_line(world: World, entry: CombatLogEntryView) -> str:
    location = world.location_name(entry.location_id) if entry.location_id else tr("combat_log_unknown")
    kind_key = f"event_type_{entry.source_kind}"
    kind = tr(kind_key)
    if kind == kind_key:
        kind = entry.source_kind
    return tr(
        "roster_profile_combat_line",
        date=_date_label(entry),
        kind=kind,
        title=entry.title,
        location=location,
        rounds=entry.round_count,
    )


def _date_label(entry: CombatLogEntryView) -> str:
    if entry.day > 0 and entry.month > 0:
        return tr("event_log_prefix_day", year=entry.year, month=entry.month, day=entry.day)
    if entry.month > 0:
        return tr("event_log_prefix_month", year=entry.year, month=entry.month)
    return tr("event_log_prefix", year=entry.year)


def _related_characters(world: World, character: Any, tag: str) -> list[Any]:
    related = []
    for target_id, tags in getattr(character, "relation_tags", {}).items():
        if tag not in tags:
            continue
        target = world.get_character_by_id(target_id)
        if target is not None:
            related.append(target)
    return sorted(related, key=lambda item: item.name)


def _relation_tag_label(tag: str) -> str:
    key = f"relation_tag_{tag}"
    label = tr(key)
    return label if label != key else tag


def _print_profile_section(ctx: UIContext, title: str, lines: list[str]) -> None:
    ctx.out.print_line()
    ctx.out.print_heading(f"  {title}")
    for line in lines:
        ctx.out.print_wrapped(f"- {line}", indent=4)
