"""Acceptance-style seeded scenario projections for report and map observability."""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import Any

import pytest

from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.reports import generate_monthly_report, generate_yearly_report
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.ui.map_renderer import (
    build_map_info,
    render_location_detail,
)
from tests.harness_test_utils import build_seeded_world, content_lines


def _extract_section(text: str, header: str) -> list[str]:
    lines = text.splitlines()
    if header not in lines:
        return []
    start = lines.index(header) + 1
    captured: list[str] = []
    for line in lines[start:]:
        if line.startswith("  ▶ "):
            break
        if line.strip() and set(line.strip()) <= {"="}:
            break
        if line.strip():
            captured.append(line)
    return captured


@lru_cache(maxsize=None)
def _capture_bundle_cached(locale: str) -> dict[str, object]:
    set_locale(locale)
    world = build_seeded_world(7)
    sim = Simulator(world, events_per_year=4, adventure_steps_per_year=2, seed=99)
    sim.advance_months(24)
    info = build_map_info(world)
    detail = render_location_detail(info, "loc_the_verdant_vale")

    if locale == "en":
        yearly_overview_header = "  ▶ World Overview"
        yearly_notable_header = "  ▶ Notable Events"
        yearly_region_header = "  ▶ Regional Events"
        monthly_notable_header = "  ▶ Notable Events"
        monthly_world_header = "  ▶ World News"
        monthly_rumors_header = "  ▶ Rumors"
    else:
        yearly_overview_header = "  ▶ 世界の概要"
        yearly_notable_header = "  ▶ 主な出来事"
        yearly_region_header = "  ▶ 地域の出来事"
        monthly_notable_header = "  ▶ 主な出来事"
        monthly_world_header = "  ▶ 世界の動き"
        monthly_rumors_header = "  ▶ 噂"

    yearly_report = sim.get_yearly_report(sim.get_latest_completed_report_year())
    monthly_report = sim.get_monthly_report(sim.world.year - 1, 3)

    return {
        "year": sim.world.year,
        "month": sim.current_month,
        "event_record_count": len(sim.world.event_records),
        "event_log_count": len(sim.world.event_log),
        "history_count": len(sim.history),
        "kind_counts": dict(sorted(Counter(r.kind for r in sim.world.event_records).items())),
        "summary_lines": content_lines(sim.get_summary()),
        "yearly_overview": _extract_section(yearly_report, yearly_overview_header),
        "yearly_notable": _extract_section(yearly_report, yearly_notable_header),
        "yearly_regions": _extract_section(yearly_report, yearly_region_header),
        "monthly_notable": _extract_section(monthly_report, monthly_notable_header),
        "monthly_world": _extract_section(monthly_report, monthly_world_header),
        "monthly_rumors": _extract_section(monthly_report, monthly_rumors_header),
        "detail_lines": content_lines(detail),
    }


def _capture_bundle(locale: str) -> dict[str, object]:
    set_locale(locale)
    return _capture_bundle_cached(locale)


def _normalize_event_tags(kind: str, tags: list[str]) -> tuple[str, ...]:
    """Normalize event tags, falling back to the event kind when none exist."""
    return tuple(tags) if tags else (kind,)


def _record_actor_ids(event_record) -> list[str]:
    """Return all actor ids referenced by an event record."""
    return (
        ([event_record.primary_actor_id] if event_record.primary_actor_id else [])
        + list(event_record.secondary_actor_ids)
    )


def _record_selection_key(event_record) -> tuple[str, str | None, str | None, tuple[str, ...]]:
    """Return the identity fields used to pin report selection behavior."""
    return (
        event_record.kind,
        event_record.location_id,
        event_record.primary_actor_id,
        tuple(event_record.secondary_actor_ids),
    )


def _memory_tags_for_location(location_state) -> tuple[str, ...]:
    """Return stable memory marker tags for a location state."""
    return tuple(
        tag
        for tag, present in (
            ("alias", bool(location_state.aliases)),
            ("memorial", bool(location_state.memorial_ids)),
            ("trace", bool(location_state.live_traces)),
        )
        if present
    )


def _selected_records_for_descriptions(
    records,
    descriptions: list[str],
    *,
    location_id: str | None = None,
) -> list[tuple[str, str | None, str | None, tuple[str, ...]]]:
    """Map report description selections back to scoped event-record identities.

    Descriptions are matched greedily in record order so duplicate descriptions
    resolve the same way the report generator emitted them.
    """
    candidate_records = [
        record for record in records if location_id is None or record.location_id == location_id
    ]
    selected: list[tuple[str, str | None, str | None, tuple[str, ...]]] = []
    used_indexes: set[int] = set()
    for description in descriptions:
        for index, record in enumerate(candidate_records):
            if index in used_indexes or record.description != description:
                continue
            selected.append(_record_selection_key(record))
            used_indexes.add(index)
            break
    return selected


def _projection_contract_for_sim(sim: Simulator) -> dict[str, Any]:
    """Capture a locale-stable projection contract for an existing simulator."""
    detail_location_id = "loc_elderroot_forest"

    yearly_year = sim.get_latest_completed_report_year()
    monthly_year = sim.world.year - 1
    monthly_month = 3
    yearly_report = generate_yearly_report(sim.world, yearly_year)
    monthly_report = generate_monthly_report(sim.world, monthly_year, monthly_month)
    yearly_records = [rec for rec in sim.world.event_records if rec.year == yearly_year]
    monthly_records = [
        rec
        for rec in sim.world.event_records
        if rec.year == monthly_year and rec.month == monthly_month
    ]

    subject_ids = sorted({
        cid
        for rec in sim.world.event_records
        for cid in _record_actor_ids(rec)
    })
    event_tags = sorted({
        _normalize_event_tags(rec.kind, rec.tags)
        for rec in sim.world.event_records
    })
    relation_tags = sorted(
        (char.char_id, other_id, tuple(tags))
        for char in sim.world.characters
        for other_id, tags in char.relation_tags.items()
        if tags
    )
    memory_tags = sorted(
        (loc.id, _memory_tags_for_location(loc))
        for loc in sim.world.grid.values()
        if _memory_tags_for_location(loc)
    )
    detail_memory_tags = next(
        (tags for loc_id, tags in memory_tags if loc_id == detail_location_id),
        (),
    )

    return {
        "summary": {
            "total_events": len(sim.world.event_records),
            "kind_counts": dict(sorted(Counter(rec.kind for rec in sim.world.event_records).items())),
        },
        "topology": {
            "site_ids": sorted(site.location_id for site in sim.world.sites),
            "route_edges": sorted(
                (
                    route.from_site_id,
                    route.to_site_id,
                    route.route_type,
                    route.blocked,
                )
                for route in sim.world.routes
            ),
        },
        "subject_ids": subject_ids,
        "event_tags": event_tags,
        "relation_tags": relation_tags,
        "memory_tags": memory_tags,
        "report_selection": {
            "yearly": {
                "year": yearly_year,
                "total_events": yearly_report.total_events,
                "deaths_this_year": yearly_report.deaths_this_year,
                "character_ids": [entry.char_id for entry in yearly_report.character_entries],
                "notable_records": _selected_records_for_descriptions(
                    yearly_records,
                    yearly_report.notable_events,
                ),
                "location_ids": [entry.location_id for entry in yearly_report.location_entries],
                "location_event_counts": {
                    entry.location_id: entry.event_count for entry in yearly_report.location_entries
                },
                "location_notable_records": {
                    entry.location_id: _selected_records_for_descriptions(
                        yearly_records,
                        entry.notable_events,
                        location_id=entry.location_id,
                    )
                    for entry in yearly_report.location_entries
                },
            },
            "monthly": {
                "year": monthly_year,
                "month": monthly_month,
                "total_events": monthly_report.total_events,
                "character_ids": [entry.char_id for entry in monthly_report.character_entries],
                "notable_records": _selected_records_for_descriptions(
                    monthly_records,
                    monthly_report.notable_events,
                ),
                "location_ids": [entry.location_id for entry in monthly_report.location_entries],
                "location_event_counts": {
                    entry.location_id: entry.event_count for entry in monthly_report.location_entries
                },
                "location_notable_records": {
                    entry.location_id: _selected_records_for_descriptions(
                        monthly_records,
                        entry.notable_events,
                        location_id=entry.location_id,
                    )
                    for entry in monthly_report.location_entries
                },
                "rumor_ids": [entry.rumor_id for entry in monthly_report.rumor_entries],
                "rumor_categories": {
                    entry.rumor_id: entry.category for entry in monthly_report.rumor_entries
                },
            },
        },
        "detail_projection": {
            "location_id": detail_location_id,
            "memory_tags": detail_memory_tags,
        },
    }


@lru_cache(maxsize=None)
def _capture_projection_contract_cached(locale: str) -> dict[str, Any]:
    """Capture the seeded, locale-stable projection contract for report/detail selection."""
    set_locale(locale)
    world = build_seeded_world(7)
    sim = Simulator(world, events_per_year=4, adventure_steps_per_year=2, seed=99)
    sim.advance_months(60)
    return _projection_contract_for_sim(sim)


def _capture_projection_contract(locale: str) -> dict[str, Any]:
    set_locale(locale)
    return _capture_projection_contract_cached(locale)


@pytest.fixture(autouse=True)
def _restore_locale():
    previous = get_locale()
    yield
    set_locale(previous)


def _assert_seeded_acceptance_bundle(bundle: dict[str, Any], *, locale: str) -> None:
    assert bundle["year"] == 1002
    assert bundle["month"] == 1
    assert bundle["event_record_count"] == 17
    assert bundle["event_log_count"] == 17
    assert bundle["history_count"] == 17
    assert bundle["kind_counts"] == {
        "aging": 12,
        "discovery": 2,
        "journey": 3,
    }
    assert bundle["monthly_notable"] == []
    assert bundle["monthly_world"] == []

    if locale == "en":
        assert bundle["summary_lines"][0] == "  SIMULATION SUMMARY - Aethoria"
        assert bundle["summary_lines"][1] == "  Final year: 1002"
        assert bundle["yearly_overview"] == ["    Total events recorded: 6"]
        assert bundle["yearly_regions"] == [
            "    Sandstone Outpost: 2 event(s)",
            "    Aethoria Capital: 1 event(s)",
            "    Obsidian Crater: 1 event(s)",
            "    Skyveil Monastery: 1 event(s)",
            "    The Grey Pass: 1 event(s)",
        ]
        assert bundle["monthly_rumors"][-1] == "    Total events: 0"
        assert any(line.startswith("    • ") for line in bundle["summary_lines"])
    else:
        assert bundle["summary_lines"][0] == "  シミュレーション要約 - Aethoria"
        assert bundle["summary_lines"][1] == "  最終年: 1002"
        assert bundle["yearly_overview"] == ["    記録イベント数: 6"]
        assert bundle["yearly_regions"] == [
            "    Sandstone Outpost: 2件の出来事",
            "    Aethoria Capital: 1件の出来事",
            "    Obsidian Crater: 1件の出来事",
            "    Skyveil Monastery: 1件の出来事",
            "    The Grey Pass: 1件の出来事",
        ]
        assert bundle["monthly_rumors"][-1] == "    イベント総数: 0"
        assert any(line.startswith("    • ") for line in bundle["summary_lines"])


def _assert_projection_contract(contract: dict[str, Any]) -> None:
    assert contract["summary"] == {
        "total_events": 45,
        "kind_counts": {
            "aging": 30,
            "battle": 1,
            "discovery": 5,
            "injury_recovery": 1,
            "journey": 5,
            "meeting": 1,
            "skill_training": 2,
        },
    }
    assert len(contract["topology"]["site_ids"]) == 25
    assert "loc_the_verdant_vale" in contract["topology"]["site_ids"]
    assert len(contract["topology"]["route_edges"]) == 40
    assert ("loc_aethoria_capital", "loc_hearthglow_town", "road", False) in contract["topology"]["route_edges"]
    assert ("loc_hearthglow_town", "loc_the_verdant_vale", "road", False) in contract["topology"]["route_edges"]
    assert ("loc_the_verdant_vale", "loc_obsidian_crater", "road", False) in contract["topology"]["route_edges"]
    assert ("aging",) in contract["event_tags"]
    assert ("discovery",) in contract["event_tags"]
    assert ("journey",) in contract["event_tags"]
    assert contract["relation_tags"] == [
        ("1738f7d9", "1e27a1c0", ("rival",)),
        ("1e27a1c0", "1738f7d9", ("rival",)),
    ]
    assert contract["detail_projection"] == {
        "location_id": "loc_elderroot_forest",
        "memory_tags": (),
    }
    assert contract["memory_tags"] == []
    assert contract["report_selection"]["yearly"]["total_events"] == 11
    assert contract["report_selection"]["yearly"]["deaths_this_year"] == 0
    assert contract["report_selection"]["monthly"] == {
        "year": 1004,
        "month": 3,
        "total_events": 0,
        "character_ids": [],
        "notable_records": [],
        "location_ids": [],
        "location_event_counts": {},
        "location_notable_records": {},
        "rumor_ids": [],
        "rumor_categories": {},
    }


def test_seeded_acceptance_bundle_matches_english_projection() -> None:
    _assert_seeded_acceptance_bundle(_capture_bundle("en"), locale="en")


def test_seeded_acceptance_bundle_matches_japanese_projection() -> None:
    _assert_seeded_acceptance_bundle(_capture_bundle("ja"), locale="ja")


def test_seeded_projection_contract_matches_expected_inputs() -> None:
    _assert_projection_contract(_capture_projection_contract("en"))


def test_seeded_projection_contract_is_locale_stable() -> None:
    assert _capture_projection_contract("ja") == _capture_projection_contract("en")


def test_midyear_save_load_preserves_projection_contract(tmp_path) -> None:
    set_locale("en")
    sim = Simulator(build_seeded_world(7), events_per_year=4, adventure_steps_per_year=2, seed=99)
    sim.advance_months(30)
    save_path = tmp_path / "midyear-seeded.json"
    remaining_months = 18

    assert save_simulation(sim, str(save_path)) is True

    restored = load_simulation(str(save_path))

    assert restored is not None
    assert restored.world.year == sim.world.year
    assert restored.current_month == sim.current_month
    assert len(restored.world.event_records) == len(sim.world.event_records)
    assert len(restored.world.event_log) == len(sim.world.event_log)

    sim.advance_months(remaining_months)
    restored.advance_months(remaining_months)

    assert _projection_contract_for_sim(restored) == _projection_contract_for_sim(sim)
