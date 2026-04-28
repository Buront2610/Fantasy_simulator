"""Relation-tag helpers for narrative context selection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, List, Optional, Sequence

if TYPE_CHECKING:
    from ..character import Character


CLOSE_RELATION_TAGS = ("spouse", "family", "friend", "savior", "rescued", "mentor", "disciple")
ADVERSARIAL_RELATION_TAGS = ("betrayer", "rival")
# Prefer the most intimate / narratively defining tie first, leaving "rival"
# as a fallback so close-loss tones win over adversarial tones when both exist.
RELATION_PRIORITY = ("spouse", "family", "savior", "rescued", "friend", "mentor", "disciple", "betrayer", "rival")


def primary_relation_tag(relation_tags: Sequence[str]) -> Optional[str]:
    for tag in RELATION_PRIORITY:
        if tag in relation_tags:
            return tag
    return relation_tags[0] if relation_tags else None


def normalize_observers(
    observer: Optional["Character" | Iterable["Character"]],
) -> Sequence["Character"]:
    if observer is None:
        return ()
    if hasattr(observer, "get_relation_tags"):
        return (observer,)
    return tuple(observer)


def collect_relation_tags(
    observer: Optional["Character" | Iterable["Character"]],
    subject_id: Optional[str],
) -> Sequence[str]:
    if subject_id is None:
        return ()
    relation_tags: List[str] = []
    for item in normalize_observers(observer):
        for tag in relation_tags_for_subject(item, subject_id):
            if tag not in relation_tags:
                relation_tags.append(tag)
    return tuple(relation_tags)


def relation_tags_for_subject(observer: "Character", subject_id: str) -> Sequence[str]:
    if hasattr(observer, "get_relationship_state"):
        relationship = observer.get_relationship_state(subject_id)
        return tuple(relationship.tags)
    if hasattr(observer, "get_relation_tags"):
        return tuple(observer.get_relation_tags(subject_id))
    return ()


def all_relation_tags(observer: "Character") -> Sequence[str]:
    if hasattr(observer, "relationship_details"):
        all_tags: List[str] = []
        for relationship in observer.relationship_details.values():
            for tag in relationship.tags:
                if tag not in all_tags:
                    all_tags.append(tag)
        return tuple(all_tags)
    relation_tags = getattr(observer, "relation_tags", None)
    if relation_tags is None:
        return ()
    all_tags: List[str] = []
    for tags in relation_tags.values():
        for tag in tags:
            if tag not in all_tags:
                all_tags.append(tag)
    return tuple(all_tags)


def derive_relation_hint(
    observers: Optional["Character" | Iterable["Character"]],
    subject_id: Optional[str] = None,
) -> Optional[str]:
    """Return the strongest relation tag, preferring directional observer semantics.

    When ``subject_id`` is provided, relation tags are read directionally from
    living observers toward the subject. When it is omitted, a single-character
    compatibility mode aggregates the character's outbound relation tags.
    """

    if observers is None:
        return None
    if subject_id is None:
        return primary_relation_tag(all_relation_tags(observers))
    return primary_relation_tag(collect_relation_tags(observers, subject_id))
