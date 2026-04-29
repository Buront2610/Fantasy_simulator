from __future__ import annotations

from fantasy_simulator.world_location_references import LocationReferenceResolver
from fantasy_simulator.world_structure_api import WorldStructureMixin


class _ResolverBackedWorld(WorldStructureMixin):
    def __init__(self) -> None:
        self._fallback_location_id_resolver = lambda name: f"fallback:{name}"
        self._location_state_defaults_resolver = (
            lambda location_id, region_type, **kwargs: {
                "prosperity": len(location_id),
                "safety": len(region_type),
                "tag_count": len(kwargs["site_tags"]),
            }
        )
        self._location_reference_resolver = LocationReferenceResolver(
            _location_ids_by_name={"Known": "loc_known"},
            _legacy_aliases={},
            _bundle_location_ids={"loc_known"},
        )

    def _site_seed_tags(self, location_id: str) -> list[str]:
        return ["capital"] if location_id == "loc_known" else []


def test_world_structure_uses_instance_resolvers_without_module_configuration() -> None:
    world = _ResolverBackedWorld()

    assert world.resolve_location_id_from_name("Known") == "loc_known"
    assert world.resolve_location_id_from_name("Unknown") == "fallback:Unknown"
    assert world.normalize_location_id(None, location_name="Unknown") == "fallback:Unknown"
    assert world.location_state_defaults("loc_known", "city") == {
        "prosperity": 9,
        "safety": 4,
        "tag_count": 1,
    }
