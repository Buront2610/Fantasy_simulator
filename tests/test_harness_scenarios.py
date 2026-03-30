"""Acceptance-style seeded scenario projections for report and map observability."""

from __future__ import annotations

import random
from collections import Counter

import pytest

from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.i18n import get_locale, set_locale
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
    return tuple(tags) if tags else (kind,)


def _capture_projection_contract(locale: str) -> dict[str, object]:
    set_locale(locale)
    world = _build_seeded_world(7)
    sim = Simulator(world, events_per_year=4, adventure_steps_per_year=2, seed=99)
    sim.advance_months(60)
    info = build_map_info(world)
    detail_location_id = "loc_elderroot_forest"

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

    yearly_year = sim.get_latest_completed_report_year()
    monthly_year = sim.world.year - 1
    monthly_month = 3
    yearly_report = sim.get_yearly_report(yearly_year)
    monthly_report = sim.get_monthly_report(monthly_year, monthly_month)

    subject_ids = sorted({
        cid
        for rec in sim.world.event_records
        for cid in ([rec.primary_actor_id] if rec.primary_actor_id else []) + list(rec.secondary_actor_ids)
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
        (
            loc.id,
            tuple(
                tag
                for tag, present in (
                    ("alias", bool(loc.aliases)),
                    ("memorial", bool(loc.memorial_ids)),
                    ("trace", bool(loc.live_traces)),
                )
                if present
            ),
        )
        for loc in sim.world.grid.values()
        if loc.aliases or loc.memorial_ids or loc.live_traces
    )
    detail_cell = next(cell for cell in info.cells.values() if cell.location_id == detail_location_id)
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
        "report_sections": {
            "yearly": {
                "year": yearly_year,
                "overview": bool(_extract_section(yearly_report, yearly_overview_header)),
                "notable": bool(_extract_section(yearly_report, yearly_notable_header)),
                "regions": bool(_extract_section(yearly_report, yearly_region_header)),
            },
            "monthly": {
                "year": monthly_year,
                "month": monthly_month,
                "notable": bool(_extract_section(monthly_report, monthly_notable_header)),
                "world": bool(_extract_section(monthly_report, monthly_world_header)),
                "rumors": bool(_extract_section(monthly_report, monthly_rumors_header)),
            },
        },
        "detail_projection": {
            "location_id": detail_location_id,
            "canonical_name": detail_cell.canonical_name,
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
    "report_sections": {
        "yearly": {
            "year": 1004,
            "overview": True,
            "notable": True,
            "regions": True,
        },
        "monthly": {
            "year": 1004,
            "month": 3,
            "notable": True,
            "world": True,
            "rumors": True,
        },
    },
    "detail_projection": {
        "location_id": "loc_elderroot_forest",
        "canonical_name": "Elderroot Forest",
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
