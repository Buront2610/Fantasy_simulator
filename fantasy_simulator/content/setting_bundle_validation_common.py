"""Shared helpers for setting-bundle validation."""

from __future__ import annotations

from typing import Callable, Iterable, List


def duplicate_values(items: Iterable[str]) -> List[str]:
    """Return duplicate string values while preserving first duplicate order."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in items:
        if item in seen and item not in duplicates:
            duplicates.append(item)
        seen.add(item)
    return duplicates


def validate_named_entries(
    values: List[str],
    *,
    source: str,
    entry_label: str,
    key_label: str | None = None,
    key_resolver: Callable[[str], str] | None = None,
) -> None:
    """Validate blank names, duplicate names, and optional duplicate inspection keys."""
    blank_values = [value for value in values if not value.strip()]
    if blank_values:
        raise ValueError(f"Setting bundle {source} contains blank {entry_label} names")

    duplicate_names = duplicate_values(values)
    if duplicate_names:
        raise ValueError(
            f"Setting bundle {source} contains duplicate {entry_label} names: {', '.join(duplicate_names)}"
        )

    if key_resolver is None:
        return

    duplicate_keys = duplicate_values([key_resolver(value) for value in values])
    if duplicate_keys:
        label = key_label or f"{entry_label} inspection keys"
        raise ValueError(
            f"Setting bundle {source} contains duplicate {label}: {', '.join(duplicate_keys)}"
        )
