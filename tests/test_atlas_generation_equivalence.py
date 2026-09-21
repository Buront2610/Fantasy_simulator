"""Generated atlas geometry must retain its exact pre-optimization serialized content."""

import hashlib
import json

import pytest

from fantasy_simulator.persistence import migration_steps
from fantasy_simulator.terrain.atlas_landmass import build_default_atlas_layout_data
from fantasy_simulator.terrain.generation import build_default_atlas_layout


@pytest.mark.parametrize("inputs,expected", [
    ({"site_coords": [(10, 8), (18, 12), (55, 22)],
      "route_coords": [((10, 8), (18, 12))], "mountain_coords": [(16, 10)]},
     "11d0829809fa59ec95ccae118c98819dd16e7c81eeb90da6ebd3f2df7bbaf08c"),
    ({"site_coords": []}, "054434bee74a794bbc70ccd88688ab64c0590b3d2e4aa37fcdcde1a679f8455a"),
    ({"site_coords": [(-4, 9), (75, 32), (36, 15)], "mountain_coords": [(-1, -1), (72, 30)]},
     "e1d6f2a1e9cd64d611f12c306bf9b42274cb73b61c59db864839b3125fd3e2a7"),
])
def test_serialized_geometry_matches_original_algorithm(inputs, expected):
    payload = build_default_atlas_layout_data(**inputs)
    assert hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest() == expected


def test_generated_layouts_remain_independent_of_input_and_each_other():
    sites = [(10, 8), (18, 12)]
    first = build_default_atlas_layout(site_coords=sites)
    second = build_default_atlas_layout(site_coords=sites)
    expected = second.to_dict()
    sites.append((55, 22))
    first.continents[0]["name"] = "Changed"
    first.continents[0]["cells"].clear()
    assert second.to_dict() == expected


def test_migration_preserves_existing_atlas_without_regenerating_it(monkeypatch):
    def unexpected_generation(*args, **kwargs):
        raise AssertionError("Existing atlas must not be regenerated")

    monkeypatch.setattr(migration_steps, "build_default_atlas_layout", unexpected_generation)
    atlas = {"canvas_w": 72, "canvas_h": 30, "continents": [], "seas": [], "mountain_ranges": []}
    site = {"site_id": "site", "x": 1, "y": 1}
    data = {"schema_version": 6, "world": {"atlas_layout": atlas, "sites": [site]}}
    result = migration_steps.migrate_v6_to_v7(data)
    assert result["world"]["atlas_layout"] is atlas
    assert result["schema_version"] == 7
    assert site["atlas_x"] >= 0 and site["atlas_y"] >= 0
