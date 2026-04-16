"""Acceptance-style seeded scenario projections for report and map observability."""

from __future__ import annotations

from collections import Counter
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


def _capture_bundle(locale: str) -> dict[str, object]:
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


def _capture_projection_contract(locale: str) -> dict[str, Any]:
    """Capture the seeded, locale-stable projection contract for report/detail selection."""
    set_locale(locale)
    world = build_seeded_world(7)
    sim = Simulator(world, events_per_year=4, adventure_steps_per_year=2, seed=99)
    sim.advance_months(60)
    return _projection_contract_for_sim(sim)


@pytest.fixture(autouse=True)
def _restore_locale():
    previous = get_locale()
    yield
    set_locale(previous)


EXPECTED_EN = {
    "year": 1002,
    "month": 1,
    "event_record_count": 22,
    "event_log_count": 22,
    "history_count": 22,
    "kind_counts": {
        "adventure_arrived": 1,
        "adventure_started": 1,
        "aging": 12,
        "discovery": 2,
        "journey": 4,
        "skill_training": 2,
    },
    "summary_lines": [
        "  SIMULATION SUMMARY - Aethoria",
        "  Final year: 1002",
        "  Total events recorded : 22",
        "  Characters alive      : 6",
        "  Characters deceased   : 0",
        "  Event breakdown:",
        "    Aging                  12 times",
        "    Journey                 4 times",
        "    Discovery               2 times",
        "    Skill training          2 times",
        "    Adventure departure     1 times",
        "    Adventure arrival       1 times",
        "  Notable moments:",
        "    • Petra Shadowmere discovered a fragment of a prophetic tablet near "
        "The Verdant Vale. The discovery will prove useful in future battles.",
        "    • Brynn Zephyrhaven discovered a hidden shrine to a forgotten deity "
        "near Sunbaked Plains. Word of the discovery spread quickly, raising their reputation.",
    ],
    "yearly_overview": ["    Total events recorded: 8"],
    "yearly_notable": [],
    "yearly_regions": [],
    "monthly_notable": [],
    "monthly_world": [],
    "monthly_rumors": [
        "    - Something happened... (doubtful)",
        "    - some time ago, Brynn Zephyrhaven discovered something Sunbaked Plains (plausible)",
        "    - some time ago, Petra Shadowmere set out traveling toward somewhere (doubtful)",
        "    - Something happened... (doubtful)",
        "    - recently, someone embarked on an adventure Sunbaked Plains (doubtful)",
        "    - recently, Brynn Zephyrhaven was involved in something somewhere (doubtful)",
        "    Total events: 0",
    ],
    "detail_lines": [
        "  | V The Verdant Vale (village)                     |",
        "  | Terrain: plains (,)                              |",
        "  | Elev:128 Moist:128 Temp:128                      |",
        "  | Safety: tense                                    |",
        "  | Danger:  68 (high)                               |",
        "  | Traffic: ++ (medium)                             |",
        "  | Pop: 0                                           |",
        "  | Prosperity: stable (50)                          |",
        "  | Mood: calm (51)                                  |",
        "  | Rumor heat: 20 (low)                             |",
    ],
}


EXPECTED_JA = {
    "year": 1002,
    "month": 1,
    "event_record_count": 22,
    "event_log_count": 22,
    "history_count": 22,
    "kind_counts": {
        "adventure_arrived": 1,
        "adventure_started": 1,
        "aging": 12,
        "discovery": 2,
        "journey": 4,
        "skill_training": 2,
    },
    "summary_lines": [
        "  シミュレーション要約 - Aethoria",
        "  最終年: 1002",
        "  記録イベント数               : 22",
        "  生存キャラクター              : 6",
        "  死亡キャラクター              : 0",
        "  イベント内訳:",
        "    加齢                     12 回",
        "    旅                       4 回",
        "    発見                      2 回",
        "    技能訓練                    2 回",
        "    冒険出発                    1 回",
        "    冒険到着                    1 回",
        "  主な出来事:",
        "    • Petra Shadowmere は The Verdant Vale 近くで 予言の石板の破片 を発見した。"
        "その発見は、これからの戦いで大いに役立つだろう。",
        "    • Brynn Zephyrhaven は Sunbaked Plains 近くで 忘れられた神を祀る隠された祠 "
        "を発見した。発見の噂はすぐに広まり、名声を高めた。",
    ],
    "yearly_overview": ["    記録イベント数: 8"],
    "yearly_notable": [],
    "yearly_regions": [],
    "monthly_notable": [],
    "monthly_world": [],
    "monthly_rumors": [
        "    - 何かが起きたらしい… (疑わしい)",
        "    - いつか、Brynn ZephyrhavenがSunbaked Plainsで何かを発見したらしい (もっともらしい)",
        "    - いつか、Petra Shadowmereがどこかへ旅立ったと聞いた (疑わしい)",
        "    - 何かが起きたらしい… (疑わしい)",
        "    - 最近、誰かがSunbaked Plainsで冒険に出たという噂がある (疑わしい)",
        "    - 最近、Brynn Zephyrhavenがどこかで何かに関わったらしい (疑わしい)",
        "    イベント総数: 0",
    ],
    "detail_lines": [
        "  | V The Verdant Vale (村)                          |",
        "  | 地形: 平原 (,)                                   |",
        "  | 標高:128 湿度:128 気温:128                       |",
        "  | 安全: 緊張                                       |",
        "  | 危険:  68 (high)                                 |",
        "  | 交通: ++ (medium)                                |",
        "  | 人数: 0                                          |",
        "  | 繁栄度: 安定 (50)                                |",
        "  | 雰囲気: 平静 (51)                                |",
        "  | 噂の熱量: 20 (low)                               |",
    ],
}


EXPECTED_PROJECTION_CONTRACT = {
    "summary": {
        "total_events": 60,
        "kind_counts": {
            "adventure_arrived": 2,
            "adventure_choice": 1,
            "adventure_discovery": 2,
            "adventure_returned": 2,
            "adventure_started": 2,
            "aging": 30,
            "battle": 1,
            "condition_worsened": 2,
            "discovery": 4,
            "injury_recovery": 1,
            "journey": 7,
            "meeting": 4,
            "skill_training": 2,
        },
    },
    "subject_ids": [
        "1738f7d9",
        "4a23d596",
        "4cdd2055",
        "8ede0d7a",
        "907a70c3",
        "a5aa3c81",
    ],
    "event_tags": [
        ("adventure_arrived",),
        ("adventure_choice",),
        ("adventure_discovery",),
        ("adventure_returned",),
        ("adventure_started",),
        ("aging",),
        ("battle",),
        ("condition_worsened",),
        ("discovery",),
        ("injury_recovery",),
        ("journey",),
        ("meeting",),
        ("skill_training",),
    ],
    "relation_tags": [
        ("8ede0d7a", "a5aa3c81", ("rival",)),
        ("a5aa3c81", "8ede0d7a", ("rival",)),
    ],
    "memory_tags": [
        ("loc_dragonbone_ridge", ("trace",)),
        ("loc_ironvein_mine", ("trace",)),
    ],
    "report_selection": {
        "yearly": {
            "year": 1004,
            "total_events": 12,
            "deaths_this_year": 0,
            "character_ids": [],
            "notable_records": [
                ("discovery", "loc_sunbaked_plains", "4cdd2055", ()),
            ],
            "location_ids": ["loc_sunbaked_plains"],
            "location_event_counts": {
                "loc_sunbaked_plains": 2,
            },
            "location_notable_records": {
                "loc_sunbaked_plains": [
                    ("discovery", "loc_sunbaked_plains", "4cdd2055", ()),
                ],
            },
        },
        "monthly": {
            "year": 1004,
            "month": 3,
            "total_events": 0,
            "character_ids": [],
            "notable_records": [],
            "location_ids": [],
            "location_event_counts": {},
            "location_notable_records": {},
            "rumor_ids": [
                "rum_51a70112a280",
                "rum_34ba06d32ef2",
                "rum_c2c960c34e8d",
                "rum_4c7e3be8b43f",
                "rum_dd4c1b0cf936",
                "rum_c2f63e561d38",
                "rum_a761dc60504c",
            ],
            "rumor_categories": {
                "rum_51a70112a280": "event",
                "rum_34ba06d32ef2": "battle",
                "rum_c2c960c34e8d": "event",
                "rum_4c7e3be8b43f": "adventure",
                "rum_dd4c1b0cf936": "event",
                "rum_c2f63e561d38": "adventure",
                "rum_a761dc60504c": "adventure",
            },
        },
    },
    "detail_projection": {
        "location_id": "loc_elderroot_forest",
        "memory_tags": (),
    },
}


def test_seeded_acceptance_bundle_matches_english_projection() -> None:
    assert _capture_bundle("en") == EXPECTED_EN


def test_seeded_acceptance_bundle_matches_japanese_projection() -> None:
    assert _capture_bundle("ja") == EXPECTED_JA


def test_seeded_projection_contract_matches_expected_inputs() -> None:
    assert _capture_projection_contract("en") == EXPECTED_PROJECTION_CONTRACT


def test_seeded_projection_contract_is_locale_stable() -> None:
    assert _capture_projection_contract("ja") == EXPECTED_PROJECTION_CONTRACT


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
