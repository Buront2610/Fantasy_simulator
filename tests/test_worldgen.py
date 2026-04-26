"""Tests for the worldgen proof of concept."""

from fantasy_simulator.terrain import Site
from fantasy_simulator.worldgen.generator import generated_sites_as_runtime_sites
from fantasy_simulator.worldgen import WorldgenConfig, build_ascii_preview, generate_world
from fantasy_simulator.worldgen.types import SiteCandidate


def test_generate_world_is_seed_stable() -> None:
    config = WorldgenConfig(width=20, height=12, seed=42, site_candidate_limit=8)
    first = generate_world(config)
    second = generate_world(config)

    assert first.to_dict() == second.to_dict()


def test_generate_world_populates_full_terrain_bounds() -> None:
    world = generate_world(WorldgenConfig(width=11, height=7, seed=3, site_candidate_limit=5))

    assert world.terrain_map.width == 11
    assert world.terrain_map.height == 7
    assert len(world.terrain_map.cells) == 77
    for (x, y), cell in world.terrain_map.cells.items():
        assert 0 <= x < world.width
        assert 0 <= y < world.height
        assert cell.x == x
        assert cell.y == y


def test_generate_world_extracts_bounded_site_candidates() -> None:
    world = generate_world(WorldgenConfig(width=24, height=14, seed=9, site_candidate_limit=6))

    assert 1 <= len(world.site_candidates) <= 6
    for candidate in world.site_candidates:
        assert 0 <= candidate.x < world.width
        assert 0 <= candidate.y < world.height
        assert candidate.rationale
        assert world.terrain_map.get(candidate.x, candidate.y) is not None


def test_generate_world_minimum_config_still_extracts_site_candidate() -> None:
    world = generate_world(WorldgenConfig(width=3, height=3, seed=0, site_candidate_limit=5))

    assert len(world.site_candidates) >= 1


def test_ascii_preview_matches_world_dimensions() -> None:
    world = generate_world(WorldgenConfig(width=13, height=9, seed=5, site_candidate_limit=4))

    preview = build_ascii_preview(world)
    rows = preview.splitlines()
    assert len(rows) == 9
    assert all(len(row) == 13 for row in rows)


def test_site_candidate_round_trip() -> None:
    candidate = SiteCandidate(
        site_id="generated_site_01",
        x=3,
        y=4,
        site_type="port",
        importance=82,
        rationale=["settlement_friendly_biome", "trade_water_access"],
    )

    restored = SiteCandidate.from_dict(candidate.to_dict())
    assert restored == candidate


def test_generated_sites_can_project_to_runtime_sites() -> None:
    world = generate_world(WorldgenConfig(width=18, height=10, seed=12, site_candidate_limit=5))

    runtime_sites = generated_sites_as_runtime_sites(world)
    assert runtime_sites
    assert all(isinstance(site, Site) for site in runtime_sites)
    assert [site.location_id for site in runtime_sites] == [candidate.site_id for candidate in world.site_candidates]


def test_worldgen_config_rejects_invalid_dimensions() -> None:
    try:
        WorldgenConfig(width=2, height=10)
    except ValueError as exc:
        assert "width" in str(exc)
    else:
        raise AssertionError("Expected width precondition to fail")

    try:
        WorldgenConfig(width=10, height=0)
    except ValueError as exc:
        assert "height" in str(exc)
    else:
        raise AssertionError("Expected height precondition to fail")


def test_worldgen_config_rejects_non_positive_site_candidate_limit() -> None:
    try:
        WorldgenConfig(width=10, height=10, site_candidate_limit=0)
    except ValueError as exc:
        assert "site_candidate_limit" in str(exc)
    else:
        raise AssertionError("Expected site_candidate_limit precondition to fail")
