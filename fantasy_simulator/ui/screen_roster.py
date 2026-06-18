"""Character roster screen flow."""

from __future__ import annotations

from typing import Any

from ..character_founder_background import render_founder_summary
from ..character_personality import (
    personality_context_from_events,
    render_personality_archetype,
    render_personality_context_factors,
    render_personality_feats,
    render_personality_summary,
)
from ..combat_log_index import CombatLogEntryView, build_combat_log_index
from ..event_rendering import render_event_record
from ..i18n import tr, tr_term
from ..world import World
from .screen_input import _get_numeric_choice
from .ui_context import UIContext, _default_ctx
from .ui_helpers import fit_display_width


RECENT_HISTORY_LIMIT = 8
PROFILE_RELATION_LIMIT = 6
PROFILE_RELATION_EVENT_LIMIT = 6
PROFILE_COMBAT_LIMIT = 5
PROFILE_RELATION_EVENT_KINDS = {
    "meeting",
    "romance",
    "marriage",
    "anniversary",
    "dying_rescued",
    "battle",
    "battle_fatal",
    "relationship_reconciliation",
    "relationship_conflict",
    "relationship_mentorship",
    "relationship_betrayal",
    "relationship_comfort",
}


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
    _print_profile_section(
        ctx,
        tr("roster_profile_relationship_history"),
        _relationship_history_lines(world, character),
    )
    _print_profile_section(ctx, tr("roster_profile_recent_history"), _history_lines(character))
    _print_profile_section(ctx, tr("roster_profile_recent_combat"), _combat_lines(world, character))
    ctx.inp.pause()


def _profile_summary_lines(world: World, character: Any) -> list[str]:
    status = tr("status_alive") if getattr(character, "alive", True) else tr("status_dead")
    injury = tr(f"injury_status_{getattr(character, 'injury_status', 'none')}")
    lines = [
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
        tr("roster_profile_temperament", archetype=render_personality_archetype(character.personality)),
    ]
    if getattr(character, "personality_feats", []):
        lines.append(tr("roster_profile_feats", feats=render_personality_feats(character.personality_feats)))
    context = personality_context_from_events(character, getattr(world, "event_records", []))
    if context.factor_keys:
        lines.append(
            tr(
                "roster_profile_current_personality",
                archetype=render_personality_archetype(context.profile),
                summary=render_personality_summary(context.profile),
                factors=render_personality_context_factors(context.factor_keys),
            )
        )
    return lines


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


def _relationship_history_lines(world: World, character: Any) -> list[str]:
    char_id = getattr(character, "char_id", "")
    if not char_id:
        return [tr("roster_profile_no_relationship_history")]
    rows: list[str] = []
    for record in reversed(list(getattr(world, "event_records", []))):
        if not _record_involves_character(record, char_id):
            continue
        render_params = getattr(record, "render_params", {})
        is_relationship_event = getattr(record, "kind", "") in PROFILE_RELATION_EVENT_KINDS
        has_relationship_factors = isinstance(render_params, dict) and "personality_affinity" in render_params
        if not is_relationship_event and not has_relationship_factors:
            continue
        rows.extend(_relationship_event_lines(world, record))
        if len(rows) >= PROFILE_RELATION_EVENT_LIMIT * 3:
            break
    return rows[:PROFILE_RELATION_EVENT_LIMIT * 3] or [tr("roster_profile_no_relationship_history")]


def _record_involves_character(record: object, char_id: str) -> bool:
    actor_ids = set(getattr(record, "secondary_actor_ids", []))
    primary_actor_id = getattr(record, "primary_actor_id", None)
    if isinstance(primary_actor_id, str) and primary_actor_id:
        actor_ids.add(primary_actor_id)
    return char_id in actor_ids


def _relationship_event_lines(world: World, record: Any) -> list[str]:
    kind = _event_kind_label(getattr(record, "kind", "generic"))
    lines = [
        tr(
            "roster_profile_relationship_event",
            date=_record_date_label(record),
            kind=kind,
            description=render_event_record(record, world=world),
        )
    ]
    cause_text = _relationship_event_cause_text(world, record)
    if cause_text:
        lines.append(cause_text)
    factor_text = _relationship_event_factor_text(record)
    if factor_text:
        lines.append(factor_text)
    return lines


def _relationship_event_cause_text(world: World, record: object) -> str:
    if not getattr(record, "cause_event_ids", []):
        return ""
    causes = [
        render_event_record(cause, world=world)
        for cause in world.get_event_causes(getattr(record, "record_id", ""))
    ]
    if not causes:
        return tr("roster_profile_relationship_cause_unavailable")
    return tr("roster_profile_relationship_cause", causes=" | ".join(causes))


def _relationship_event_factor_text(record: object) -> str:
    render_params = getattr(record, "render_params", {})
    if not isinstance(render_params, dict):
        return ""
    parts = []
    if "personality_affinity" in render_params:
        parts.append(
            tr(
                "event_log_personality_reason",
                affinity=render_params.get("personality_affinity", 0),
                factors=render_params.get("personality_factors", tr("event_log_no_personality_factors")),
                delta=render_params.get("relationship_delta", 0),
            )
        )
    catalyst_bonus = int(render_params.get("relationship_catalyst_bonus", 0) or 0)
    if catalyst_bonus:
        parts.append(
            tr(
                "event_log_catalyst_reason",
                bonus=catalyst_bonus,
                factors=render_params.get("relationship_catalyst_factors", tr("event_log_no_catalyst_factors")),
            )
        )
    if not parts:
        return ""
    return tr("roster_profile_relationship_factor", factors=" / ".join(parts))


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


def _record_date_label(record: object) -> str:
    year = int(getattr(record, "year", 0) or 0)
    month = int(getattr(record, "month", 0) or 0)
    day = int(getattr(record, "day", 0) or 0)
    if day > 0 and month > 0:
        return tr("event_log_prefix_day", year=year, month=month, day=day)
    if month > 0:
        return tr("event_log_prefix_month", year=year, month=month)
    return tr("event_log_prefix", year=year)


def _event_kind_label(kind: str) -> str:
    key = f"event_type_{kind}"
    label = tr(key)
    return label if label != key else kind


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
