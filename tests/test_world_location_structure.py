from __future__ import annotations

from dataclasses import dataclass, field

from fantasy_simulator.world import World
from fantasy_simulator.world_location_structure import (
    copy_location_runtime_state,
    default_location_entries,
    grid_matches_site_seeds,
    register_location,
    serialized_grid_is_compatible_with_site_seeds,
)


@dataclass
class _Location:
    id: str
    canonical_name: str
    description: str
    region_type: str
    x: int
    y: int
    prosperity: int = 50
    safety: int = 50
    mood: int = 50
    danger: int = 20
    traffic: int = 30
    rumor_heat: int = 0
    road_condition: int = 70
    visited: bool = False
    controlling_faction_id: str | None = None
    recent_event_ids: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    generated_endonym: str = ""
    memorial_ids: list[str] = field(default_factory=list)
    live_traces: list[dict[str, object]] = field(default_factory=list)


@dataclass
class _Seed:
    location_id: str
    name: str
    description: str
    region_type: str
    x: int
    y: int
    tags: list[str] = field(default_factory=list)

    def as_world_data_entry(self) -> tuple[str, str, str, str, int, int]:
        return (self.location_id, self.name, self.description, self.region_type, self.x, self.y)


def test_register_location_replaces_coordinate_and_id_indexes() -> None:
    grid = {}
    name_index = {}
    id_index = {}
    old = _Location("loc_old", "Old", "Old desc", "city", 0, 0)
    replacement = _Location("loc_new", "New", "New desc", "village", 0, 0)

    register_location(grid=grid, location_name_index=name_index, location_id_index=id_index, location=old)
    register_location(grid=grid, location_name_index=name_index, location_id_index=id_index, location=replacement)

    assert grid[(0, 0)] is replacement
    assert "Old" not in name_index
    assert "loc_old" not in id_index
    assert name_index["New"] is replacement
    assert id_index["loc_new"] is replacement


def test_copy_location_runtime_state_preserves_structural_name_and_endonym() -> None:
    source = _Location(
        "loc_a",
        "Old Name",
        "Old desc",
        "city",
        0,
        0,
        prosperity=12,
        aliases=["Old Alias", "Shared"],
        generated_endonym="Old Endonym",
        recent_event_ids=["evt_1"],
        memorial_ids=["mem_1"],
        live_traces=[{"text": "seen", "nested": {"depth": 1}}],
    )
    target = _Location(
        "loc_a",
        "New Name",
        "New desc",
        "city",
        0,
        0,
        aliases=["Shared", "Structural Alias"],
        generated_endonym="New Endonym",
    )

    copy_location_runtime_state(source, target)

    assert target.canonical_name == "New Name"
    assert target.prosperity == 12
    assert target.generated_endonym == "New Endonym"
    assert target.aliases == ["Shared", "Structural Alias", "Old Alias"]
    assert target.recent_event_ids == ["evt_1"]
    assert target.memorial_ids == ["mem_1"]
    assert target.live_traces == [{"text": "seen", "nested": {"depth": 1}}]
    assert target.live_traces is not source.live_traces
    assert target.live_traces[0]["nested"] is not source.live_traces[0]["nested"]

    source.live_traces[0]["nested"]["depth"] = 99

    assert target.live_traces == [{"text": "seen", "nested": {"depth": 1}}]


def test_bundle_grid_compatibility_helpers_use_in_bounds_site_seed_shape() -> None:
    seeds = [
        _Seed("loc_a", "A", "Alpha", "city", 0, 0),
        _Seed("loc_b", "B", "Beta", "village", 9, 9),
    ]
    grid_locations = [_Location("loc_a", "A", "Alpha", "city", 0, 0)]

    assert default_location_entries(seeds, width=2, height=2) == [("loc_a", "A", "Alpha", "city", 0, 0)]
    assert grid_matches_site_seeds(site_seeds=seeds, grid_locations=grid_locations, width=2, height=2)
    assert serialized_grid_is_compatible_with_site_seeds(
        [{"id": "legacy_a", "canonical_name": "A"}],
        site_seeds=seeds,
        normalize_location_id=lambda loc_id, name: "loc_a" if name == "A" else loc_id,
    )
    assert not serialized_grid_is_compatible_with_site_seeds(
        [{"id": "missing", "canonical_name": "Missing"}],
        site_seeds=seeds,
        normalize_location_id=lambda loc_id, _name: loc_id,
    )


def test_world_structure_resolvers_are_instance_scoped() -> None:
    world_a = World(_skip_defaults=True)
    world_b = World(_skip_defaults=True)
    world_a._fallback_location_id_resolver = lambda name: f"a:{name}"
    world_b._fallback_location_id_resolver = lambda name: f"b:{name}"
    world_a._location_state_defaults_resolver = lambda *_args, **_kwargs: {"danger": 11}
    world_b._location_state_defaults_resolver = lambda *_args, **_kwargs: {"danger": 22}

    assert world_a.resolve_location_id_from_name("Unmapped Place") == "a:Unmapped Place"
    assert world_b.resolve_location_id_from_name("Unmapped Place") == "b:Unmapped Place"
    assert world_a.location_state_defaults("loc_unknown", "wilds") == {"danger": 11}
    assert world_b.location_state_defaults("loc_unknown", "wilds") == {"danger": 22}
