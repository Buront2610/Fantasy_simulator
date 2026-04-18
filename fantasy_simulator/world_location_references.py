"""Location reference normalization and repair helpers for ``World``.

This module isolates bundle-backed location ID policy from the rest of the
world aggregate so save/load compatibility and runtime orchestration stay
separate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Container, Dict, Iterable, Optional

from .content.setting_bundle import legacy_location_id_alias

FallbackLocationIdResolver = Callable[[str], str]


@dataclass(slots=True)
class LocationReferenceResolver:
    """Normalize and repair persisted location references against bundle data."""

    _location_ids_by_name: Dict[str, str]
    _legacy_aliases: Dict[str, str]
    _bundle_location_ids: set[str]

    @classmethod
    def from_site_seeds(cls, site_seeds: Iterable[Any]) -> "LocationReferenceResolver":
        location_ids_by_name: Dict[str, str] = {}
        legacy_aliases: Dict[str, str] = {}
        bundle_location_ids: set[str] = set()
        for seed in site_seeds:
            location_ids_by_name[seed.name] = seed.location_id
            bundle_location_ids.add(seed.location_id)
            legacy_id = legacy_location_id_alias(seed.name)
            if legacy_id != seed.location_id:
                legacy_aliases[legacy_id] = seed.location_id
        return cls(
            _location_ids_by_name=location_ids_by_name,
            _legacy_aliases=legacy_aliases,
            _bundle_location_ids=bundle_location_ids,
        )

    def bundle_location_id_for_name(self, name: str) -> str | None:
        """Resolve a location name through bundle site seeds only."""
        return self._location_ids_by_name.get(name)

    def resolve_location_id_from_name(self, name: str, *, fallback_resolver: FallbackLocationIdResolver) -> str:
        """Resolve a location name through bundle data with slug fallback."""
        return self.bundle_location_id_for_name(name) or fallback_resolver(name)

    def legacy_location_id_aliases(self) -> Dict[str, str]:
        """Return compatibility aliases that should map to canonical IDs."""
        return dict(self._legacy_aliases)

    def normalize_location_id(
        self,
        location_id: Optional[str],
        *,
        location_name: str | None = None,
        fallback_resolver: FallbackLocationIdResolver | None = None,
    ) -> Optional[str]:
        """Normalize persisted location IDs against the active bundle policy."""
        if location_id:
            aliased = self._legacy_aliases.get(location_id)
            if aliased is not None:
                return aliased
            if location_id in self._bundle_location_ids:
                return location_id
            if location_name is not None:
                bundle_location_id = self.bundle_location_id_for_name(location_name)
                if bundle_location_id is not None:
                    return bundle_location_id
            return location_id
        if location_name is not None:
            if fallback_resolver is None:
                return self.bundle_location_id_for_name(location_name)
            return self.resolve_location_id_from_name(location_name, fallback_resolver=fallback_resolver)
        return location_id

    def repair_location_reference(
        self,
        location_id: Optional[str],
        *,
        known_location_ids: Container[str],
        location_name: str | None = None,
        required: bool = False,
        fallback_location_id: str | None = None,
        fallback_resolver: FallbackLocationIdResolver | None = None,
    ) -> Optional[str]:
        """Resolve a location reference to a current-world location when possible."""
        normalized = self.normalize_location_id(
            location_id,
            location_name=location_name,
            fallback_resolver=fallback_resolver,
        )
        if normalized in known_location_ids:
            return normalized
        if required:
            if fallback_location_id is not None:
                return fallback_location_id
            return ""
        return None
