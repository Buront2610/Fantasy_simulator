"""Acceptance-style seeded scenario projections for report and map observability."""

from __future__ import annotations

import random
from collections import Counter
from typing import Any

import pytest

from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.reports import generate_monthly_report, generate_yearly_report
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.ui.map_renderer import build_map_info, render_location_detail
from fantasy_simulator.world import World


def _build_seeded_world(seed: int, n_chars: int = 6) -> World:
    rng = random.Random(seed)
    world = World()
    creator = CharacterCreator()
    location_ids = [loc.id for loc in world.grid.values() if loc.region_type != "dungeon"]
    for _ in range(n_chars):
        char = creator.create_random(rng=rng)
        char.location_id = rng.choice(location_ids)
        world.add_character(char)
    return world


def _content_lines(text: str) -> list[str]:
    content: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if set(stripped) <= {"="}:
            continue
        if stripped.startswith("+") and set(stripped) <= {"+", "-"}:
            continue
        content.append(line)
    return content


def _extract_section(text: str, header: str) -> list[str]:
    lines = text.splitlines()
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
    world = _build_seeded_world(7)
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
        "summary_lines": _content_lines(sim.get_summary()),
        "yearly_overview": _extract_section(yearly_report, yearly_overview_header),
        "yearly_notable": _extract_section(yearly_report, yearly_notable_header),
        "yearly_regions": _extract_section(yearly_report, yearly_region_header),
        "monthly_notable": _extract_section(monthly_report, monthly_notable_header),
        "monthly_world": _extract_section(monthly_report, monthly_world_header),
        "monthly_rumors": _extract_section(monthly_report, monthly_rumors_header),
        "detail_lines": _content_lines(detail),
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


def _capture_projection_contract(locale: str) -> dict[str, Any]:
    """Capture the seeded, locale-stable projection contract for report/detail selection."""
    set_locale(locale)
    world = _build_seeded_world(7)
    sim = Simulator(world, events_per_year=4, adventure_steps_per_year=2, seed=99)
    sim.advance_months(60)
    detail_location_id = "loc_elderroot_forest"

    yearly_year = sim.get_latest_completed_report_year()
    monthly_year = sim.world.year - 1
    monthly_month = 3
    yearly_report = generate_yearly_report(world, yearly_year)
    monthly_report = generate_monthly_report(world, monthly_year, monthly_month)
    yearly_records = [rec for rec in world.event_records if rec.year == yearly_year]
    monthly_records = [
        rec
        for rec in world.event_records
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


@pytest.fixture(autouse=True)
def _restore_locale():
    previous = get_locale()
    yield
    set_locale(previous)


EXPECTED_EN = {
    "year": 1002,
    "month": 1,
    "event_record_count": 14,
    "event_log_count": 14,
    "history_count": 11,
    "kind_counts": {
        "adventure_arrived": 1,
        "adventure_discovery": 1,
        "adventure_started": 1,
        "battle": 1,
        "condition_worsened": 2,
        "discovery": 1,
        "journey": 4,
        "meeting": 2,
        "skill_training": 1,
    },
    "summary_lines": [
        "  SIMULATION SUMMARY - Aethoria",
        "  Final year: 1002",
        "  Total events recorded : 14",
        "  Characters alive      : 6",
        "  Characters deceased   : 0",
        "  Event breakdown:",
        "    Journey                 4 times",
        "    Condition worsened      2 times",
        "    Meeting                 2 times",
        "    Skill training          1 times",
        "    Adventure departure     1 times",
        "    Adventure arrival       1 times",
        "    Adventure discovery     1 times",
        "    Discovery               1 times",
        "    Battle                  1 times",
        "  Notable moments:",
        "    • Brynn Zephyrhaven discovered a vein of star-metal ore near Sunbaked Plains. "
        "Word of the discovery spread quickly, raising their reputation.",
    ],
    "yearly_overview": ["    Total events recorded: 9"],
    "yearly_notable": [
        "    - Jorin Riverstone's condition worsened to serious.",
        "    - Brynn Zephyrhaven discovered a vein of star-metal ore near Sunbaked Plains. "
        "Word of the discovery spread quickly, raising their reputation.",
        "    - Talia Coldwater defeated Casia Riverstone. Casia Riverstone was injured in the fight.",
    ],
    "yearly_regions": [
        "    Sunbaked Plains: Brynn Zephyrhaven discovered a vein of star-metal ore near Sunbaked Plains. "
        "Word of the discovery spread quickly, raising their reputation.",
        "    The Grey Pass: Jorin Riverstone's condition worsened to serious.",
        "    The Verdant Vale: Talia Coldwater defeated Casia Riverstone. Casia Riverstone was injured in the fight.",
    ],
    "monthly_notable": [
        "    - Halia Underhill & Petra Shadowmere set out from Millhaven toward Elderroot Forest.",
        "    - Halia Underhill reached Elderroot Forest and began the expedition.",
        "    - Halia Underhill scouted the area around Elderroot Forest.",
    ],
    "monthly_world": [
        "    Elderroot Forest: Halia Underhill reached Elderroot Forest and began the expedition.",
        "    Elderroot Forest: Halia Underhill scouted the area around Elderroot Forest.",
        "    Millhaven: Halia Underhill & Petra Shadowmere set out from Millhaven toward Elderroot Forest.",
    ],
    "monthly_rumors": [
        "    - some time ago, someone was involved in something somewhere (plausible)",
        "    - some time ago, someone embarked on an adventure somewhere (doubtful)",
        "    - Something happened... (doubtful)",
        "    - some time ago, someone embarked on an adventure somewhere (doubtful)",
        "    Total events: 3",
    ],
    "detail_lines": [
        "  | V The Verdant Vale (village)                     |",
        "  | Terrain: plains (,)                              |",
        "  | Elev:128 Moist:128 Temp:128                      |",
        "  | Safety: tense                                    |",
        "  | Danger:  58 (medium)                             |",
        "  | Traffic: ++ (medium)                             |",
        "  | Pop: 3                                           |",
        "  | Prosperity: stable (50)                          |",
        "  | Mood: anxious (44)                               |",
        "  | Rumor heat: 24 (low)                             |",
    ],
}


EXPECTED_JA = {
    "year": 1002,
    "month": 1,
    "event_record_count": 14,
    "event_log_count": 14,
    "history_count": 11,
    "kind_counts": {
        "adventure_arrived": 1,
        "adventure_discovery": 1,
        "adventure_started": 1,
        "battle": 1,
        "condition_worsened": 2,
        "discovery": 1,
        "journey": 4,
        "meeting": 2,
        "skill_training": 1,
    },
    "summary_lines": [
        "  シミュレーション要約 - Aethoria",
        "  最終年: 1002",
        "  記録イベント数               : 14",
        "  生存キャラクター              : 6",
        "  死亡キャラクター              : 0",
        "  イベント内訳:",
        "    旅                       4 回",
        "    容態悪化                    2 回",
        "    出会い                     2 回",
        "    技能訓練                    1 回",
        "    冒険出発                    1 回",
        "    冒険到着                    1 回",
        "    冒険中の発見                  1 回",
        "    発見                      1 回",
        "    戦闘                      1 回",
        "  主な出来事:",
        "    • Brynn Zephyrhaven は Sunbaked Plains 近くで 星鉄鉱の鉱脈 を発見した。"
        "発見の噂はすぐに広まり、名声を高めた。",
    ],
    "yearly_overview": ["    記録イベント数: 9"],
    "yearly_notable": [
        "    - Jorin Riverstone の容態が悪化し、重傷になった。",
        "    - Brynn Zephyrhaven は Sunbaked Plains 近くで 星鉄鉱の鉱脈 を発見した。"
        "発見の噂はすぐに広まり、名声を高めた。",
        "    - Talia Coldwater は Casia Riverstone に勝利した。 "
        "Casia Riverstone は戦いで負傷した。",
    ],
    "yearly_regions": [
        "    Sunbaked Plains: Brynn Zephyrhaven は Sunbaked Plains 近くで 星鉄鉱の鉱脈 を発見した。"
        "発見の噂はすぐに広まり、名声を高めた。",
        "    The Grey Pass: Jorin Riverstone の容態が悪化し、重傷になった。",
        "    The Verdant Vale: Talia Coldwater は Casia Riverstone に勝利した。 "
        "Casia Riverstone は戦いで負傷した。",
    ],
    "monthly_notable": [
        "    - Halia Underhill & Petra Shadowmere は Millhaven を出発し、Elderroot Forest へ向かった。",
        "    - Halia Underhill は Elderroot Forest に到着し、探索を始めた。",
        "    - Halia Underhill は Elderroot Forest 周辺を偵察した。",
    ],
    "monthly_world": [
        "    Elderroot Forest: Halia Underhill は Elderroot Forest に到着し、探索を始めた。",
        "    Elderroot Forest: Halia Underhill は Elderroot Forest 周辺を偵察した。",
        "    Millhaven: Halia Underhill & Petra Shadowmere は Millhaven を出発し、Elderroot Forest へ向かった。",
    ],
    "monthly_rumors": [
        "    - いつか、誰かがどこかで何かに関わったらしい (もっともらしい)",
        "    - いつか、誰かがどこかで冒険に出たという噂がある (疑わしい)",
        "    - 何かが起きたらしい… (疑わしい)",
        "    - いつか、誰かがどこかで冒険に出たという噂がある (疑わしい)",
        "    イベント総数: 3",
    ],
    "detail_lines": [
        "  | V The Verdant Vale (村)                          |",
        "  | 地形: 平原 (,)                                   |",
        "  | 標高:128 湿度:128 気温:128                       |",
        "  | 安全: 緊張                                       |",
        "  | 危険:  58 (medium)                               |",
        "  | 交通: ++ (medium)                                |",
        "  | 人数: 3                                          |",
        "  | 繁栄度: 安定 (50)                                |",
        "  | 雰囲気: 不安 (44)                                |",
        "  | 噂の熱量: 24 (low)                               |",
    ],
}


EXPECTED_PROJECTION_CONTRACT = {
    "summary": {
        "total_events": 39,
        "kind_counts": {
            "adventure_arrived": 2,
            "adventure_choice": 1,
            "adventure_discovery": 2,
            "adventure_retreated": 1,
            "adventure_returned": 1,
            "adventure_started": 2,
            "battle": 3,
            "condition_worsened": 3,
            "death": 1,
            "discovery": 2,
            "injury_recovery": 1,
            "journey": 9,
            "meeting": 4,
            "skill_training": 7,
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
        ("adventure_retreated",),
        ("adventure_returned",),
        ("adventure_started",),
        ("battle",),
        ("condition_worsened",),
        ("death",),
        ("discovery",),
        ("injury_recovery",),
        ("journey",),
        ("meeting",),
        ("skill_training",),
    ],
    "relation_tags": [
        ("1738f7d9", "8ede0d7a", ("rival",)),
        ("8ede0d7a", "1738f7d9", ("rival",)),
    ],
    "memory_tags": [
        ("loc_dragonbone_ridge", ("trace",)),
        ("loc_elderroot_forest", ("trace",)),
    ],
    "report_selection": {
        "yearly": {
            "year": 1004,
            "total_events": 7,
            "deaths_this_year": 0,
            "character_ids": [],
            "notable_records": [
                ("battle", "loc_the_verdant_vale", "8ede0d7a", ("1738f7d9",)),
                ("battle", "loc_the_verdant_vale", "8ede0d7a", ("1738f7d9",)),
            ],
            "location_ids": ["loc_the_verdant_vale"],
            "location_event_counts": {"loc_the_verdant_vale": 3},
            "location_notable_records": {
                "loc_the_verdant_vale": [
                    ("battle", "loc_the_verdant_vale", "8ede0d7a", ("1738f7d9",)),
                    ("battle", "loc_the_verdant_vale", "8ede0d7a", ("1738f7d9",)),
                ],
            },
        },
        "monthly": {
            "year": 1004,
            "month": 3,
            "total_events": 1,
            "character_ids": [],
            "notable_records": [
                ("battle", "loc_the_verdant_vale", "8ede0d7a", ("1738f7d9",)),
            ],
            "location_ids": ["loc_the_verdant_vale"],
            "location_event_counts": {"loc_the_verdant_vale": 1},
            "location_notable_records": {
                "loc_the_verdant_vale": [
                    ("battle", "loc_the_verdant_vale", "8ede0d7a", ("1738f7d9",)),
                ],
            },
            "rumor_ids": ["rum_f17c0793e07a"],
            "rumor_categories": {"rum_f17c0793e07a": "battle"},
        },
    },
    "detail_projection": {
        "location_id": "loc_elderroot_forest",
        "memory_tags": ("trace",),
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
