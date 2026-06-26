"""Copy-based update helpers for canonical world event records."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, Iterable

from .models import LOCATION_TAG_PREFIX, WorldEventRecord


def event_record_with_location_id(
    record: WorldEventRecord,
    location_id: str | None,
) -> WorldEventRecord:
    """Return a copy of *record* with a normalized location reference."""
    return replace(record, location_id=location_id)


def _normalize_render_param_location_ids(
    render_params: dict[str, Any],
    normalize_location_id: Callable[[str | None], str | None],
) -> dict[str, Any]:
    normalized = dict(render_params)
    for key in ("location_id", "from_location_id", "to_location_id"):
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = normalize_location_id(value)

    endpoint_location_ids = normalized.get("endpoint_location_ids")
    if isinstance(endpoint_location_ids, list):
        normalized["endpoint_location_ids"] = [
            normalized_location_id
            for value in endpoint_location_ids
            if isinstance(value, str)
            for normalized_location_id in [normalize_location_id(value)]
            if normalized_location_id is not None
        ]
    return normalized


def _normalize_location_tags(
    tags: Iterable[str],
    normalize_location_id: Callable[[str | None], str | None],
) -> list[str]:
    normalized_tags: list[str] = []
    for tag in tags:
        if tag.startswith(LOCATION_TAG_PREFIX):
            normalized_location_id = normalize_location_id(tag[len(LOCATION_TAG_PREFIX):])
            if normalized_location_id is None:
                continue
            tag = f"{LOCATION_TAG_PREFIX}{normalized_location_id}"
        if tag not in normalized_tags:
            normalized_tags.append(tag)
    return normalized_tags


def _normalize_location_impacts(
    impacts: Iterable[dict[str, Any]],
    normalize_location_id: Callable[[str | None], str | None],
) -> list[dict[str, Any]]:
    normalized_impacts: list[dict[str, Any]] = []
    for impact in impacts:
        normalized_impact = dict(impact)
        if normalized_impact.get("target_type") == "location":
            target_id = normalized_impact.get("target_id")
            if isinstance(target_id, str):
                normalized_target_id = normalize_location_id(target_id)
                if normalized_target_id is None:
                    continue
                normalized_impact["target_id"] = normalized_target_id
        normalized_impacts.append(normalized_impact)
    return normalized_impacts


def event_record_with_normalized_location_references(
    record: WorldEventRecord,
    normalize_location_id: Callable[[str | None], str | None],
) -> WorldEventRecord:
    """Return a copy with every canonical location reference normalized."""
    return replace(
        record,
        location_id=normalize_location_id(record.location_id),
        render_params=_normalize_render_param_location_ids(record.render_params, normalize_location_id),
        tags=_normalize_location_tags(record.tags, normalize_location_id),
        impacts=_normalize_location_impacts(record.impacts, normalize_location_id),
    )


def normalize_event_record_locations(
    records: Iterable[WorldEventRecord],
    normalize_location_id: Callable[[str | None], str | None],
) -> list[WorldEventRecord]:
    """Return event record copies with location IDs normalized."""
    return [
        event_record_with_normalized_location_references(record, normalize_location_id)
        for record in records
    ]


def event_record_with_added_tags(
    record: WorldEventRecord,
    tags: Iterable[str],
) -> WorldEventRecord:
    """Return a copy of *record* with unique appended tags."""
    return replace(record, tags=list(dict.fromkeys([*record.tags, *tags])))


def _assert_render_param_matches(
    render_params: dict[str, Any],
    key: str,
    canonical_value: Any,
    *,
    record_id: str,
) -> None:
    if not canonical_value or key not in render_params:
        return
    if render_params[key] != canonical_value:
        raise ValueError(
            f"render_params[{key!r}] conflicts with canonical {key} "
            f"for event {record_id!r}: {render_params[key]!r} != {canonical_value!r}"
        )


def event_record_with_semantic_render_params(record: WorldEventRecord) -> WorldEventRecord:
    """Return a copy whose render params include stable actor/location IDs when renderable."""
    if not record.summary_key and not record.render_params:
        return record
    render_params = dict(record.render_params)
    actor_ids: list[str] = []
    if record.primary_actor_id:
        actor_ids.append(record.primary_actor_id)
    actor_ids.extend(record.secondary_actor_ids)
    _assert_render_param_matches(
        render_params,
        "primary_actor_id",
        record.primary_actor_id,
        record_id=record.record_id,
    )
    _assert_render_param_matches(
        render_params,
        "secondary_actor_ids",
        list(record.secondary_actor_ids),
        record_id=record.record_id,
    )
    _assert_render_param_matches(
        render_params,
        "actor_ids",
        list(actor_ids),
        record_id=record.record_id,
    )
    _assert_render_param_matches(
        render_params,
        "location_id",
        record.location_id,
        record_id=record.record_id,
    )
    if record.primary_actor_id and not render_params.get("primary_actor_id"):
        render_params["primary_actor_id"] = record.primary_actor_id
    if record.secondary_actor_ids and "secondary_actor_ids" not in render_params:
        render_params["secondary_actor_ids"] = list(record.secondary_actor_ids)
    if actor_ids and "actor_ids" not in render_params:
        render_params["actor_ids"] = list(actor_ids)
    has_semantic_location_params = any(
        key.endswith("_location_id") or key.endswith("_location_ids")
        for key in render_params
    )
    if record.location_id and "location_id" not in render_params and not has_semantic_location_params:
        render_params["location_id"] = record.location_id
    return replace(record, render_params=render_params)
