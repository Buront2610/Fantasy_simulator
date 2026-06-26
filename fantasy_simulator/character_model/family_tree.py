"""Family-tree read models projected from canonical events and relation tags."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..i18n import tr, tr_term
from .founder_background import render_founder_summary


@dataclass(frozen=True)
class FamilyMemberView:
    char_id: str
    name: str
    age: int
    race: str
    job: str
    alive: bool


@dataclass(frozen=True)
class FamilyCoupleView:
    partner_ids: tuple[str, str]
    partners: tuple[FamilyMemberView | None, FamilyMemberView | None]
    marriage_years: tuple[int, ...] = ()
    child_ids: tuple[str, ...] = ()
    children: tuple[FamilyMemberView | None, ...] = ()
    relationship_score: int | None = None
    active_marriage: bool = False

    @property
    def child_count(self) -> int:
        return len(self.child_ids)

    @property
    def has_marriage(self) -> bool:
        return bool(self.marriage_years or self.active_marriage)


@dataclass(frozen=True)
class FamilyFounderView:
    member: FamilyMemberView
    summary: str


@dataclass(frozen=True)
class FamilyTreeView:
    couples: tuple[FamilyCoupleView, ...]
    founders: tuple[FamilyFounderView, ...]
    married_couple_count: int
    child_count: int
    children_per_married_couple: float
    married_couples_with_children: int


def build_family_tree(world: Any) -> FamilyTreeView:
    """Build a family tree projection without adding persistent schema fields."""
    characters = list(getattr(world, "characters", []))
    members = {_char_id(character): _member_view(character) for character in characters}
    characters_by_id = {_char_id(character): character for character in characters}
    marriage_years: dict[tuple[str, str], list[int]] = {}
    active_marriages: set[tuple[str, str]] = set()
    children_by_couple: dict[tuple[str, str], set[str]] = {}

    for record in getattr(world, "event_records", []):
        if getattr(record, "kind", "") == "marriage":
            partner_ids = _record_actor_ids(record)
            if len(partner_ids) >= 2:
                marriage_years.setdefault(_couple_key(partner_ids[0], partner_ids[1]), []).append(
                    int(getattr(record, "year", 0) or 0)
                )
        elif getattr(record, "kind", "") == "birth":
            child_id, parent_ids = _birth_record_family_ids(record)
            if child_id and len(parent_ids) >= 2:
                children_by_couple.setdefault(_couple_key(parent_ids[0], parent_ids[1]), set()).add(child_id)

    _add_relation_tag_children(characters, children_by_couple)
    for character in characters:
        spouse_id = getattr(character, "spouse_id", None)
        if isinstance(spouse_id, str) and spouse_id:
            active_marriages.add(_couple_key(_char_id(character), spouse_id))

    all_couple_keys = sorted(
        set(marriage_years) | set(active_marriages) | set(children_by_couple),
        key=lambda key: (
            min(marriage_years.get(key, [999999])),
            _member_name(members.get(key[0]), key[0]),
            _member_name(members.get(key[1]), key[1]),
        ),
    )
    couples = tuple(
        _couple_view(key, members, characters_by_id, marriage_years, children_by_couple, active_marriages)
        for key in all_couple_keys
    )
    founders = _founder_views(characters, members)
    married_couples = [couple for couple in couples if couple.has_marriage]
    total_children = sum(couple.child_count for couple in married_couples)
    average = total_children / len(married_couples) if married_couples else 0.0
    return FamilyTreeView(
        couples=couples,
        founders=founders,
        married_couple_count=len(married_couples),
        child_count=total_children,
        children_per_married_couple=round(average, 2),
        married_couples_with_children=sum(1 for couple in married_couples if couple.child_count),
    )


def _couple_view(
    key: tuple[str, str],
    members: dict[str, FamilyMemberView],
    characters_by_id: dict[str, Any],
    marriage_years: dict[tuple[str, str], list[int]],
    children_by_couple: dict[tuple[str, str], set[str]],
    active_marriages: set[tuple[str, str]],
) -> FamilyCoupleView:
    child_ids = tuple(
        sorted(children_by_couple.get(key, set()), key=lambda child_id: _child_sort_key(members, child_id))
    )
    return FamilyCoupleView(
        partner_ids=key,
        partners=(members.get(key[0]), members.get(key[1])),
        marriage_years=tuple(sorted(dict.fromkeys(marriage_years.get(key, [])))),
        child_ids=child_ids,
        children=tuple(members.get(child_id) for child_id in child_ids),
        relationship_score=_couple_relationship_score(characters_by_id, key),
        active_marriage=key in active_marriages,
    )


def render_family_tree_lines(world: Any) -> list[str]:
    view = build_family_tree(world)
    lines = [
        tr("family_tree_header"),
        tr(
            "family_tree_summary",
            couples=view.married_couple_count,
            children=view.child_count,
            average=f"{view.children_per_married_couple:.2f}",
            couples_with_children=view.married_couples_with_children,
        ),
    ]
    if not view.couples and not view.founders:
        lines.append(tr("family_tree_empty"))
        return lines
    if view.founders:
        lines.append(tr("family_tree_founders_header"))
        for founder in view.founders:
            lines.append(
                tr(
                    "family_tree_founder_line",
                    member=_member_label(founder.member),
                    summary=founder.summary,
                )
            )
    for couple in view.couples:
        lines.append(_render_couple_line(couple))
        if not couple.children:
            lines.append(f"    {tr('family_tree_no_children')}")
            continue
        for child in couple.children:
            lines.append(f"    {tr('family_tree_child_prefix')}: {_member_label(child)}")
    return lines


def _member_view(character: Any) -> FamilyMemberView:
    return FamilyMemberView(
        char_id=_char_id(character),
        name=str(getattr(character, "name", "")),
        age=int(getattr(character, "age", 0) or 0),
        race=str(getattr(character, "race", "")),
        job=str(getattr(character, "job", "")),
        alive=bool(getattr(character, "alive", True)),
    )


def _char_id(character: Any) -> str:
    return str(getattr(character, "char_id", ""))


def _couple_key(first_id: str, second_id: str) -> tuple[str, str]:
    ordered = sorted((first_id, second_id))
    return (ordered[0], ordered[1])


def _record_actor_ids(record: Any) -> list[str]:
    actor_ids = []
    primary_actor_id = getattr(record, "primary_actor_id", None)
    if isinstance(primary_actor_id, str) and primary_actor_id:
        actor_ids.append(primary_actor_id)
    actor_ids.extend(
        actor_id for actor_id in getattr(record, "secondary_actor_ids", [])
        if isinstance(actor_id, str) and actor_id
    )
    return list(dict.fromkeys(actor_ids))


def _birth_record_family_ids(record: Any) -> tuple[str, list[str]]:
    render_params = getattr(record, "render_params", {})
    child_id = ""
    parent_ids: list[str] = []
    if isinstance(render_params, dict):
        raw_child_id = render_params.get("child_id")
        if isinstance(raw_child_id, str):
            child_id = raw_child_id
        raw_parent_ids = render_params.get("parent_ids", [])
        if isinstance(raw_parent_ids, list):
            parent_ids = [parent_id for parent_id in raw_parent_ids if isinstance(parent_id, str) and parent_id]
    actor_ids = _record_actor_ids(record)
    if not child_id and actor_ids:
        child_id = actor_ids[0]
    if len(parent_ids) < 2 and len(actor_ids) >= 3:
        parent_ids = actor_ids[1:3]
    return child_id, list(dict.fromkeys(parent_ids))


def _add_relation_tag_children(characters: Iterable[Any], children_by_couple: dict[tuple[str, str], set[str]]) -> None:
    for child in characters:
        parent_ids = [
            target_id for target_id, tags in getattr(child, "relation_tags", {}).items()
            if isinstance(target_id, str) and "parent" in tags
        ]
        if len(parent_ids) >= 2:
            children_by_couple.setdefault(_couple_key(parent_ids[0], parent_ids[1]), set()).add(_char_id(child))


def _founder_views(
    characters: Iterable[Any],
    members: dict[str, FamilyMemberView],
) -> tuple[FamilyFounderView, ...]:
    founders: list[FamilyFounderView] = []
    for character in characters:
        background = getattr(character, "founder_background", None)
        member = members.get(_char_id(character))
        if not isinstance(background, dict) or member is None:
            continue
        if _has_parent_tag(character):
            continue
        founders.append(FamilyFounderView(member=member, summary=render_founder_summary(background)))
    return tuple(sorted(founders, key=lambda founder: founder.member.name))


def _has_parent_tag(character: Any) -> bool:
    return any(
        isinstance(tags, list) and "parent" in tags
        for tags in getattr(character, "relation_tags", {}).values()
    )


def _member_name(member: FamilyMemberView | None, fallback_id: str) -> str:
    return member.name if member is not None else fallback_id


def _child_sort_key(members: dict[str, FamilyMemberView], child_id: str) -> tuple[int, str]:
    member = members.get(child_id)
    return (member.age if member is not None else 9999, _member_name(member, child_id))


def _render_couple_line(couple: FamilyCoupleView) -> str:
    years = ", ".join(str(year) for year in couple.marriage_years)
    if years:
        status = tr("family_tree_married_years", years=years)
    elif couple.active_marriage:
        status = tr("family_tree_active_marriage")
    else:
        status = tr("family_tree_family_pair")
    return tr(
        "family_tree_couple_line",
        partner1=_member_label(couple.partners[0]),
        partner2=_member_label(couple.partners[1]),
        status=status,
        count=couple.child_count,
        relationship=_relationship_label(couple.relationship_score),
    )


def _member_label(member: FamilyMemberView | None) -> str:
    if member is None:
        return tr("family_tree_unknown_member")
    status = tr("status_alive") if member.alive else tr("status_dead")
    return tr(
        "family_tree_member_label",
        name=member.name,
        race=tr_term(member.race),
        job=tr_term(member.job),
        age=member.age,
        status=status,
    )


def _couple_relationship_score(characters_by_id: dict[str, Any], key: tuple[str, str]) -> int | None:
    first = characters_by_id.get(key[0])
    second = characters_by_id.get(key[1])
    if first is None or second is None:
        return None
    first_score = getattr(first, "relationships", {}).get(key[1])
    second_score = getattr(second, "relationships", {}).get(key[0])
    scores = [score for score in (first_score, second_score) if isinstance(score, int)]
    if not scores:
        return None
    return round(sum(scores) / len(scores))


def _relationship_label(score: int | None) -> str:
    if score is None:
        return tr("family_tree_relationship_unknown")
    return f"{score:+d}"
