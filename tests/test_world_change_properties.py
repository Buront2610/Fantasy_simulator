"""Property-based invariant checks for PR-K world-change primitives."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from fantasy_simulator.world_event.models import WorldEventRecord
from fantasy_simulator.world_core.ids import LocationId, RouteId
from fantasy_simulator.terrain import RouteEdge, TerrainCell, TerrainMap
from fantasy_simulator.world_change import (
    LocationRenameUpdate,
    MutateTerrainCellCommand,
    RouteUpdate,
    WorldChangeSet,
    apply_world_change_set,
    build_terrain_cell_mutation_change_set,
)
from fantasy_simulator.world_change.state_machines import transition_world_scores


hypothesis = pytest.importorskip("hypothesis")
given = hypothesis.given
settings = hypothesis.settings
st = hypothesis.strategies


@dataclass
class _Location:
    id: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)


def _record(record_id: str = "rec_property") -> WorldEventRecord:
    return WorldEventRecord(record_id=record_id, kind="property", year=1001, description="Property change.")


def _record_event(records: list[WorldEventRecord]):
    def record_event(record: WorldEventRecord) -> WorldEventRecord:
        records.append(record)
        return record

    return record_event


@settings(max_examples=40)
@given(st.booleans(), st.lists(st.booleans(), min_size=1, max_size=12))
def test_route_block_sequence_preserves_identity_and_endpoints(
    initial_blocked: bool,
    requested_states: list[bool],
) -> None:
    route = RouteEdge("route_a_b", "loc_a", "loc_b", blocked=initial_blocked)
    records: list[WorldEventRecord] = []

    for index, requested in enumerate(requested_states):
        if route.blocked == requested:
            continue
        change_set = WorldChangeSet(
            events=(_record(f"rec_route_{index}"),),
            route_updates=(
                RouteUpdate(
                    route_id=RouteId(route.route_id),
                    old_blocked=route.blocked,
                    new_blocked=requested,
                ),
            ),
        )

        apply_world_change_set(change_set, routes=[route], record_event=_record_event(records))

        assert route.route_id == "route_a_b"
        assert route.from_site_id == "loc_a"
        assert route.to_site_id == "loc_b"
        assert route.blocked == requested


@settings(max_examples=40)
@given(
    st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters=(" ", "-")),
            min_size=1,
            max_size=20,
        ),
        min_size=1,
        max_size=12,
    )
)
def test_location_rename_sequence_preserves_location_id_and_alias_bound(names: list[str]) -> None:
    location = _Location("loc_capital", "Aethoria Capital")
    location_index = {location.id: location}
    location_name_index = {location.canonical_name: location}
    max_aliases = 4
    records: list[WorldEventRecord] = []

    for index, raw_name in enumerate(names):
        new_name = raw_name.strip()
        if not new_name or new_name == location.canonical_name:
            continue
        old_name = location.canonical_name
        old_aliases = tuple(location.aliases)
        new_aliases = list(location.aliases)
        if old_name not in new_aliases and len(new_aliases) < max_aliases:
            new_aliases.append(old_name)

        change_set = WorldChangeSet(
            events=(_record(f"rec_rename_{index}"),),
            location_updates=(
                LocationRenameUpdate(
                    location_id=LocationId(location.id),
                    old_name=old_name,
                    new_name=new_name,
                    old_aliases=old_aliases,
                    new_aliases=tuple(new_aliases),
                ),
            ),
        )

        apply_world_change_set(
            change_set,
            routes=[],
            location_index=location_index,
            location_name_index=location_name_index,
            record_event=_record_event(records),
        )

        assert location.id == "loc_capital"
        assert location_index == {"loc_capital": location}
        assert location_name_index[location.canonical_name] is location
        assert len(location.aliases) <= max_aliases


@settings(max_examples=40)
@given(
    st.dictionaries(
        st.sampled_from(["prosperity", "safety", "traffic", "mood"]),
        st.integers(min_value=0, max_value=100),
        min_size=4,
        max_size=4,
    ),
    st.dictionaries(
        st.sampled_from(["prosperity", "safety", "traffic", "mood"]),
        st.integers(min_value=-250, max_value=250),
        min_size=1,
        max_size=4,
    ),
)
def test_world_score_transitions_are_bounded(scores: dict[str, int], deltas: dict[str, int]) -> None:
    transitions = transition_world_scores(scores, deltas)

    for transition in transitions:
        assert transition.score_key in scores
        assert 0 <= transition.old_value <= 100
        assert 0 <= transition.new_value <= 100
        assert transition.delta == transition.new_value - transition.old_value


@settings(max_examples=40)
@given(
    st.sampled_from(["forest", "plains", "swamp"]),
    st.integers(min_value=-50, max_value=300),
    st.integers(min_value=-50, max_value=300),
    st.integers(min_value=-50, max_value=300),
)
def test_terrain_cell_mutation_scalar_commands_enforce_byte_range(
    biome: str,
    elevation: int,
    moisture: int,
    temperature: int,
) -> None:
    terrain_map = TerrainMap(width=1, height=1)
    terrain_map.set_cell(TerrainCell(x=0, y=0, biome="forest", elevation=128, moisture=128, temperature=128))
    cell = terrain_map.get(0, 0)
    assert cell is not None
    command = MutateTerrainCellCommand(
        x=0,
        y=0,
        biome=biome,
        elevation=elevation,
        moisture=moisture,
        temperature=temperature,
        year=1001,
    )

    if not (0 <= elevation <= 255 and 0 <= moisture <= 255 and 0 <= temperature <= 255):
        with pytest.raises(ValueError, match="must be between 0 and 255"):
            build_terrain_cell_mutation_change_set(
                command,
                terrain_map=terrain_map,
                allowed_biomes={"forest", "plains", "swamp"},
                describe=lambda _summary_key, _params, fallback: fallback,
            )
        return

    change_set = build_terrain_cell_mutation_change_set(
        command,
        terrain_map=terrain_map,
        allowed_biomes={"forest", "plains", "swamp"},
        describe=lambda _summary_key, _params, fallback: fallback,
    )
    if change_set is not None:
        apply_world_change_set(change_set, routes=[], terrain_map=terrain_map, record_event=_record_event([]))

    assert cell.biome == biome
    assert 0 <= cell.elevation <= 255
    assert 0 <= cell.moisture <= 255
    assert 0 <= cell.temperature <= 255
