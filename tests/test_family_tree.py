from __future__ import annotations

from fantasy_simulator.character import Character
from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.family_tree import build_family_tree, render_family_tree_lines
from fantasy_simulator.world import World


def _character(name: str, char_id: str, *, age: int = 30) -> Character:
    return Character(
        name=name,
        age=age,
        gender="male",
        race="Human",
        job="Warrior",
        char_id=char_id,
        location_id="loc_aethoria_capital",
    )


def test_family_tree_projects_marriages_births_and_average_children() -> None:
    world = World()
    parent_a = _character("Ari", "parent_a")
    parent_b = _character("Bea", "parent_b")
    parent_c = _character("Cai", "parent_c")
    parent_d = _character("Dia", "parent_d")
    child_1 = _character("Eli", "child_1", age=4)
    child_2 = _character("Fia", "child_2", age=1)
    for character in (parent_a, parent_b, parent_c, parent_d, child_1, child_2):
        world.add_character(character)
    parent_a.spouse_id = parent_b.char_id
    parent_b.spouse_id = parent_a.char_id
    parent_a.update_mutual_relationship(parent_b, 42)
    parent_c.spouse_id = parent_d.char_id
    parent_d.spouse_id = parent_c.char_id
    world.event_records = [
        WorldEventRecord(
            record_id="marriage_ab",
            kind="marriage",
            year=1001,
            primary_actor_id=parent_a.char_id,
            secondary_actor_ids=[parent_b.char_id],
        ),
        WorldEventRecord(
            record_id="marriage_cd",
            kind="marriage",
            year=1002,
            primary_actor_id=parent_c.char_id,
            secondary_actor_ids=[parent_d.char_id],
        ),
        WorldEventRecord(
            record_id="birth_1",
            kind="birth",
            year=1003,
            primary_actor_id=child_1.char_id,
            secondary_actor_ids=[parent_a.char_id, parent_b.char_id],
            render_params={"child_id": child_1.char_id, "parent_ids": [parent_a.char_id, parent_b.char_id]},
        ),
        WorldEventRecord(
            record_id="birth_2",
            kind="birth",
            year=1004,
            primary_actor_id=child_2.char_id,
            secondary_actor_ids=[parent_a.char_id, parent_b.char_id],
            render_params={"child_id": child_2.char_id, "parent_ids": [parent_a.char_id, parent_b.char_id]},
        ),
    ]

    tree = build_family_tree(world)

    assert tree.married_couple_count == 2
    assert tree.child_count == 2
    assert tree.children_per_married_couple == 1.0
    assert tree.married_couples_with_children == 1
    assert [couple.child_count for couple in tree.couples] == [2, 0]
    assert tree.couples[0].relationship_score == 42


def test_family_tree_uses_relation_tags_when_birth_record_is_missing() -> None:
    world = World()
    parent_a = _character("Ari", "parent_a")
    parent_b = _character("Bea", "parent_b")
    child = _character("Eli", "child", age=3)
    child.add_relation_tag(parent_a.char_id, "parent")
    child.add_relation_tag(parent_b.char_id, "parent")
    for character in (parent_a, parent_b, child):
        world.add_character(character)
    parent_a.update_relationship(parent_b.char_id, 8)
    parent_b.update_relationship(parent_a.char_id, 10)

    tree = build_family_tree(world)

    assert tree.couples[0].partner_ids == ("parent_a", "parent_b")
    assert tree.couples[0].child_ids == ("child",)
    assert tree.married_couple_count == 0


def test_render_family_tree_lines_includes_summary_and_children() -> None:
    world = World()
    parent_a = _character("Ari", "parent_a")
    parent_b = _character("Bea", "parent_b")
    child = _character("Eli", "child", age=2)
    for character in (parent_a, parent_b, child):
        world.add_character(character)
    parent_a.update_relationship(parent_b.char_id, 8)
    parent_b.update_relationship(parent_a.char_id, 10)
    world.event_records = [
        WorldEventRecord(
            record_id="marriage",
            kind="marriage",
            year=1001,
            primary_actor_id=parent_a.char_id,
            secondary_actor_ids=[parent_b.char_id],
        ),
        WorldEventRecord(
            record_id="birth",
            kind="birth",
            year=1002,
            render_params={"child_id": child.char_id, "parent_ids": [parent_a.char_id, parent_b.char_id]},
        ),
    ]

    lines = render_family_tree_lines(world)

    assert lines[0] == "FAMILY TREE"
    assert "avg children/couple: 1.00" in lines[1]
    assert "bond=+9" in lines[2]
    assert any("Ari" in line and "Bea" in line for line in lines)
    assert any("Eli" in line for line in lines)
