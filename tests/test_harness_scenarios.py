"""Acceptance-style seeded scenario projections for report and map observability."""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from typing import Any

import pytest

from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.observation import (
    build_era_timeline_projection,
    build_location_history_projection,
    build_route_status_projection,
    build_war_map_projection,
    build_world_change_report_projection,
)
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.reports import generate_monthly_report, generate_yearly_report
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.ui.map_renderer import (
    build_map_info,
    render_location_detail,
)
from fantasy_simulator.ui.view_models import build_monthly_report_card_view, build_world_dashboard_view
from fantasy_simulator.world import World
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


def _capture_simulation_statistics(world_seed: int) -> dict[str, int]:
    """Capture broad seeded-run balance signals without pinning exact stories."""
    set_locale("en")
    sim = Simulator(build_seeded_world(world_seed), events_per_year=4, adventure_steps_per_year=2, seed=99)
    sim.advance_months(24)
    kind_counts = Counter(record.kind for record in sim.world.event_records)
    active_months = {
        (record.year, record.month)
        for record in sim.world.event_records
    }
    return {
        "event_count": len(sim.world.event_records),
        "non_aging_event_count": sum(count for kind, count in kind_counts.items() if kind != "aging"),
        "kind_diversity": len(kind_counts),
        "active_month_count": len(active_months),
        "alive_count": sum(1 for char in sim.world.characters if char.alive),
        "active_rumor_count": sum(1 for rumor in sim.world.rumors if not rumor.is_expired),
    }


def _build_pr_k_characterization_sim() -> Simulator:
    """Build a fixed PR-K world-change scenario that spans the observation surfaces."""
    world = World()
    route = next(
        candidate
        for candidate in world.routes
        if {candidate.from_site_id, candidate.to_site_id} == {
            "loc_aethoria_capital",
            "loc_hearthglow_town",
        }
    )
    records = [
        world.apply_route_blocked_change(route.route_id, True, month=3, day=1),
        world.apply_location_rename_change("loc_aethoria_capital", "Aethoria March", month=3, day=2),
        world.apply_war_declaration(
            "stormwatch_wardens",
            "silverbrook_merchant_league",
            location_ids=("loc_aethoria_capital", "loc_silverbrook"),
            month=3,
            day=3,
        ),
        world.apply_controlling_faction_change(
            "loc_silverbrook",
            "stormwatch_wardens",
            month=3,
            day=4,
        ),
        world.apply_terrain_cell_change(
            2,
            2,
            biome="forest",
            elevation=180,
            location_id="loc_aethoria_capital",
            month=3,
            day=5,
        ),
        world.apply_era_shift(
            "age_of_reckoning",
            authored_era_keys={"age_of_embers", "age_of_reckoning"},
            month=3,
            day=6,
        ),
        world.apply_civilization_phase_drift(
            "crisis",
            score_deltas={"safety": -10, "prosperity": -5},
            month=3,
            day=7,
        ),
    ]
    assert all(record is not None for record in records)
    return Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=20260604)


def _pr_k_characterization_contract(sim: Simulator) -> dict[str, Any]:
    """Capture the locale-stable PR-K projection contract for a prepared simulator."""
    world = sim.world
    route = next(
        candidate
        for candidate in world.routes
        if {candidate.from_site_id, candidate.to_site_id} == {
            "loc_aethoria_capital",
            "loc_hearthglow_town",
        }
    )
    year = world.year
    month = 3
    records = world.event_records
    report_projection = build_world_change_report_projection(
        event_records=records,
        year=year,
        month=month,
    )
    monthly_card = build_monthly_report_card_view(world, year, month)
    dashboard = build_world_dashboard_view(world, current_month=month)
    route_projection = build_route_status_projection(
        routes=world.routes,
        event_records=records,
        route_id=route.route_id,
    )
    location_history = build_location_history_projection(
        locations=world.grid.values(),
        event_records=records,
        location_id="loc_aethoria_capital",
    )
    war_projection = build_war_map_projection(event_records=records)
    era_projection = build_era_timeline_projection(event_records=records)
    map_info = build_map_info(world)
    tracked_cell_locations = {
        route.from_site_id,
        route.to_site_id,
        "loc_aethoria_capital",
        "loc_silverbrook",
    }
    map_categories = sorted(
        (cell.location_id, cell.recent_world_change_categories)
        for cell in map_info.cells.values()
        if cell.location_id in tracked_cell_locations
    )

    return {
        "event_kinds": [record.kind for record in records],
        "report_counts": [
            (count.category, count.count) for count in report_projection.counts_by_category
        ],
        "report_entries": [
            (entry.kind, entry.category, entry.location_ids) for entry in report_projection.entries
        ],
        "monthly_card": {
            "entries": [
                (entry.kind, entry.category) for entry in report_projection.entries
            ],
            "threads": [
                (thread.category, thread.count, tuple(thread.location_names))
                for thread in monthly_card.world_change_threads
            ],
            "highlighted_locations": monthly_card.highlighted_locations,
        },
        "dashboard": {
            "route_closures": [
                (entry.route_id, entry.from_location_id, entry.to_location_id)
                for entry in dashboard.current_route_closures
            ],
            "active_wars": [
                (entry.aggressor_faction_id, entry.target_faction_id)
                for entry in dashboard.active_wars
            ],
            "current_occupations": [
                (entry.location_id, entry.controlling_faction_id)
                for entry in dashboard.current_occupations
            ],
            "era_status": (
                dashboard.era_status.era_id,
                dashboard.era_status.civilization_phase,
            ) if dashboard.era_status is not None else None,
            "world_change_categories": [
                entry.category for entry in dashboard.world_change_entries
            ],
            "follow_up_keys": [entry.key for entry in dashboard.follow_up_actions],
        },
        "route_projection": {
            "status": route_projection.status,
            "history": [(entry.kind, entry.blocked) for entry in route_projection.history],
        },
        "location_history": {
            "name": location_history.official_name,
            "aliases": location_history.aliases,
            "rename_transitions": [
                (entry.old_name, entry.new_name) for entry in location_history.rename_history
            ],
        },
        "war_projection": {
            "active_wars": [
                (entry.aggressor_faction_id, entry.target_faction_id)
                for entry in war_projection.active_wars
            ],
            "current_occupations": [
                (entry.location_id, entry.controlling_faction_id)
                for entry in war_projection.current_occupations
            ],
        },
        "era_projection": {
            "current_era_id": era_projection.current_era_id,
            "current_civilization_phase": era_projection.current_civilization_phase,
            "kinds": [entry.kind for entry in era_projection.entries],
        },
        "map_categories": map_categories,
    }


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


def test_seeded_long_run_statistics_stay_in_expected_bounds() -> None:
    summaries = [_capture_simulation_statistics(seed) for seed in (7, 8, 9)]

    for summary in summaries:
        assert 12 <= summary["event_count"] <= 36
        assert 4 <= summary["non_aging_event_count"] <= 20
        assert summary["kind_diversity"] >= 3
        assert summary["active_month_count"] >= 6
        assert summary["alive_count"] >= 3
        assert summary["active_rumor_count"] <= 20

    assert sum(summary["non_aging_event_count"] for summary in summaries) >= 20


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


def test_pr_k_characterization_golden_contract_covers_world_change_surfaces() -> None:
    set_locale("en")
    sim = _build_pr_k_characterization_sim()

    contract = _pr_k_characterization_contract(sim)

    assert contract["event_kinds"] == [
        "route_blocked",
        "location_renamed",
        "war_declared",
        "location_faction_changed",
        "terrain_cell_mutated",
        "era_shifted",
        "civilization_phase_drifted",
    ]
    assert contract["report_counts"] == [
        ("civilization", 1),
        ("era", 1),
        ("location", 1),
        ("occupation", 1),
        ("route", 1),
        ("terrain", 1),
        ("war", 1),
    ]
    assert contract["report_entries"] == [
        ("route_blocked", "route", ("loc_aethoria_capital", "loc_hearthglow_town")),
        ("location_renamed", "location", ("loc_aethoria_capital",)),
        ("war_declared", "war", ("loc_aethoria_capital", "loc_silverbrook")),
        ("location_faction_changed", "occupation", ("loc_silverbrook",)),
        ("terrain_cell_mutated", "terrain", ("loc_aethoria_capital",)),
        ("era_shifted", "era", ()),
        ("civilization_phase_drifted", "civilization", ()),
    ]
    assert contract["monthly_card"] == {
        "entries": [
            ("route_blocked", "route"),
            ("location_renamed", "location"),
            ("war_declared", "war"),
            ("location_faction_changed", "occupation"),
            ("terrain_cell_mutated", "terrain"),
            ("era_shifted", "era"),
            ("civilization_phase_drifted", "civilization"),
        ],
        "threads": [
            ("civilization", 1, ()),
            ("era", 1, ()),
            ("location", 1, ("Aethoria March",)),
        ],
        "highlighted_locations": ["Aethoria March", "Silverbrook", "Hearthglow Town"],
    }
    assert contract["dashboard"] == {
        "route_closures": [
            (
                "route_024",
                "loc_aethoria_capital",
                "loc_hearthglow_town",
            )
        ],
        "active_wars": [("stormwatch_wardens", "silverbrook_merchant_league")],
        "current_occupations": [("loc_silverbrook", "stormwatch_wardens")],
        "era_status": ("age_of_reckoning", "crisis"),
        "world_change_categories": [
            "route",
            "location",
            "war",
            "occupation",
            "terrain",
            "era",
            "civilization",
        ],
        "follow_up_keys": [
            "inspect_route_closure",
            "inspect_occupation",
            "review_active_war",
            "review_world_change",
            "review_world_change",
        ],
    }
    assert contract["route_projection"] == {
        "status": "blocked",
        "history": [("route_blocked", True)],
    }
    assert contract["location_history"] == {
        "name": "Aethoria March",
        "aliases": ("Aethoria Capital",),
        "rename_transitions": [("Aethoria Capital", "Aethoria March")],
    }
    assert contract["war_projection"] == {
        "active_wars": [("stormwatch_wardens", "silverbrook_merchant_league")],
        "current_occupations": [("loc_silverbrook", "stormwatch_wardens")],
    }
    assert contract["era_projection"] == {
        "current_era_id": "age_of_reckoning",
        "current_civilization_phase": "crisis",
        "kinds": ["era_shifted", "civilization_phase_drifted"],
    }
    assert contract["map_categories"] == [
        ("loc_aethoria_capital", ("route", "location", "war", "terrain")),
        ("loc_hearthglow_town", ("route",)),
        ("loc_silverbrook", ("war", "occupation")),
    ]


def test_pr_k_characterization_golden_contract_survives_save_load(tmp_path) -> None:
    set_locale("en")
    sim = _build_pr_k_characterization_sim()
    save_path = tmp_path / "pr-k-characterization-golden.json"

    assert save_simulation(sim, str(save_path)) is True

    restored = load_simulation(str(save_path))

    assert restored is not None
    assert _pr_k_characterization_contract(restored) == _pr_k_characterization_contract(sim)
