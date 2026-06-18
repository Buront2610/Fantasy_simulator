from __future__ import annotations

import random

import pytest

from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.simulation.world_change_driver import generate_war_arc_pulse
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.testing.world_metrics import collect_world_health_metrics, write_world_health_report
from fantasy_simulator.world import World

from .balance_expectations import (
    MIN_ALIVE_AFTER_HEALTH_RUN,
    MIN_TOTAL_IMMIGRATIONS,
    MIN_TOTAL_COMBAT_EVENTS,
    MIN_TOTAL_COMBAT_ROUNDS,
    MIN_TOTAL_MAGIC_COMBAT_ACTIONS,
    MIN_TOTAL_MARRIAGES,
    MIN_TOTAL_ADVENTURE_RISK_OUTCOMES,
    MAX_WORLD_HEALTH_EVENT_RECORDS,
    MAX_WORLD_HEALTH_SAVE_JSON_BYTES,
    WORLD_HEALTH_SEEDS,
    WORLD_HEALTH_STARTING_POPULATION,
    WORLD_HEALTH_YEARS,
)


_COMBAT_LOG_KEYS = {
    "round_number",
    "actor_id",
    "target_id",
    "action_kind",
    "skill_key",
    "dice",
    "modifier",
    "target_number",
    "attack_total",
    "defense_total",
    "damage",
    "actor_vitality",
    "target_vitality",
    "outcome",
}


class _BattlePulseRng:
    def __init__(self) -> None:
        self._bits = 1000

    def choice(self, values):
        return list(values)[0]

    def random(self) -> float:
        return 0.95

    def randint(self, lo: int, hi: int) -> int:
        return hi

    def getrandbits(self, _bits: int) -> int:
        self._bits += 1
        return self._bits


class _EndPulseRng(_BattlePulseRng):
    def random(self) -> float:
        return 0.0


def _build_health_world(seed: int) -> World:
    rng = random.Random(seed)
    world = World()
    creator = CharacterCreator()
    locations = [loc.id for loc in world.grid.values() if loc.region_type != "dungeon"]
    for _ in range(WORLD_HEALTH_STARTING_POPULATION):
        char = creator.create_random(rng=rng)
        char.location_id = rng.choice(locations)
        world.add_character(char, rng=rng)
    return world


def _assert_structured_combat_log(combat_log: list[dict]) -> None:
    assert combat_log
    assert _COMBAT_LOG_KEYS <= set(combat_log[0])
    assert any(entry["dice"] >= 1 for entry in combat_log)
    assert any(entry["damage"] >= 0 for entry in combat_log)
    assert all(entry["attack_total"] >= entry["dice"] for entry in combat_log)
    assert all(entry["defense_total"] == entry["target_number"] for entry in combat_log)
    assert all(entry["outcome"] in {"miss", "checked", "advantage", "decisive"} for entry in combat_log)


@pytest.mark.simulation_stats
def test_world_health_stats_keep_world_alive_and_social(tmp_path) -> None:
    metrics_by_seed = {}
    total_adventure_risk_outcomes = 0
    total_marriages = 0
    total_immigrations = 0
    total_combat_events = 0
    total_combat_rounds = 0
    total_magic_actions = 0
    max_event_records = 0
    max_save_bytes = 0
    for seed in WORLD_HEALTH_SEEDS:
        sim = Simulator(
            _build_health_world(seed),
            events_per_year=8,
            adventure_steps_per_year=3,
            world_changes_per_year=1,
            seed=seed,
        )
        sim.advance_years(WORLD_HEALTH_YEARS)
        metrics = collect_world_health_metrics(sim.world)
        metrics_by_seed[str(seed)] = metrics
        total_adventure_risk_outcomes += sum(
            metrics["adventure_outcomes"].get(outcome, 0)
            for outcome in ("death", "injury", "retreat")
        )
        total_marriages += metrics["marriage_count"]
        total_immigrations += metrics["immigration_count"]
        total_combat_events += metrics["combat_event_count"]
        total_combat_rounds += metrics["combat_round_count"]
        total_magic_actions += metrics["magic_combat_action_count"]
        max_event_records = max(max_event_records, metrics["event_record_count"])
        max_save_bytes = max(max_save_bytes, metrics["estimated_world_save_json_bytes"])

        assert metrics["alive"] >= MIN_ALIVE_AFTER_HEALTH_RUN, (
            f"[world-health] seed={seed} alive={metrics['alive']} "
            f"(expected >= {MIN_ALIVE_AFTER_HEALTH_RUN}). "
            "Meaning: population maintenance is failing and the world trends toward extinction."
        )

    write_world_health_report(metrics_by_seed, tmp_path / ".world_health_report.json")
    assert total_immigrations >= MIN_TOTAL_IMMIGRATIONS, (
        f"[world-health] immigration_count={total_immigrations} "
        f"(expected >= {MIN_TOTAL_IMMIGRATIONS} across seeds {WORLD_HEALTH_SEEDS}). "
        "Meaning: the migration stabilizer is not visibly participating in long-run history."
    )
    assert total_marriages >= MIN_TOTAL_MARRIAGES, (
        f"[world-health] marriage_count={total_marriages} "
        f"(expected >= {MIN_TOTAL_MARRIAGES} across seeds {WORLD_HEALTH_SEEDS}). "
        "Meaning: relationships are not reaching commitment often enough for generational play."
    )
    assert total_adventure_risk_outcomes >= MIN_TOTAL_ADVENTURE_RISK_OUTCOMES, (
        f"[world-health] adventure_risk_outcomes={total_adventure_risk_outcomes} "
        f"(expected >= {MIN_TOTAL_ADVENTURE_RISK_OUTCOMES} across seeds {WORLD_HEALTH_SEEDS}). "
        "Meaning: adventures have drifted back into consequence-free outcomes."
    )
    assert total_combat_events >= MIN_TOTAL_COMBAT_EVENTS, (
        f"[world-health] combat_event_count={total_combat_events} "
        f"(expected >= {MIN_TOTAL_COMBAT_EVENTS} across seeds {WORLD_HEALTH_SEEDS}). "
        "Meaning: battle events are no longer visibly participating in long-run history."
    )
    assert total_combat_rounds >= MIN_TOTAL_COMBAT_ROUNDS, (
        f"[world-health] combat_round_count={total_combat_rounds} "
        f"(expected >= {MIN_TOTAL_COMBAT_ROUNDS} across seeds {WORLD_HEALTH_SEEDS}). "
        "Meaning: combat may have regressed to single-roll resolution without round logs."
    )
    assert total_magic_actions >= MIN_TOTAL_MAGIC_COMBAT_ACTIONS, (
        f"[world-health] magic_combat_action_count={total_magic_actions} "
        f"(expected >= {MIN_TOTAL_MAGIC_COMBAT_ACTIONS} across seeds {WORLD_HEALTH_SEEDS}). "
        "Meaning: magic skills are no longer connected to combat outcomes."
    )
    assert max_event_records <= MAX_WORLD_HEALTH_EVENT_RECORDS, (
        f"[world-health] event_record_count={max_event_records} "
        f"(expected <= {MAX_WORLD_HEALTH_EVENT_RECORDS} for {WORLD_HEALTH_YEARS}y smoke). "
        "Meaning: canonical history growth may be running away and long saves will bloat."
    )
    assert max_save_bytes <= MAX_WORLD_HEALTH_SAVE_JSON_BYTES, (
        f"[world-health] estimated_world_save_json_bytes={max_save_bytes} "
        f"(expected <= {MAX_WORLD_HEALTH_SAVE_JSON_BYTES} for {WORLD_HEALTH_YEARS}y smoke). "
        "Meaning: save footprint growth needs investigation before longer playtests."
    )


@pytest.mark.simulation_stats
def test_playtest_war_arc_records_combat_and_causal_chain() -> None:
    world = World()
    declared = world.apply_war_declaration(
        "stormwatch_wardens",
        "silverbrook_merchant_league",
        location_ids=("loc_aethoria_capital", "loc_silverbrook"),
        month=2,
        day=3,
        cause_key="playtest_border_incident",
    )

    battle = generate_war_arc_pulse(world, month=3, day=4, rng=_BattlePulseRng())
    ended = generate_war_arc_pulse(world, month=4, day=5, rng=_EndPulseRng())
    metrics = collect_world_health_metrics(world)

    assert battle is not None
    assert battle.kind == "war_battle"
    assert battle.render_params["cause_event_id"] == declared.record_id
    assert battle.render_params["arc_id"] == world.world_arcs[0].arc_id
    _assert_structured_combat_log(battle.render_params["combat_log"])

    assert ended is not None
    assert ended.kind == "war_ended"
    assert ended.render_params["cause_event_id"] == battle.record_id
    assert world.world_arcs[0].phase == "resolved"
    assert world.world_arcs[0].related_event_ids == [
        declared.record_id,
        battle.record_id,
        ended.record_id,
    ]
    assert metrics["war_battle_count"] == 1
    assert metrics["combat_event_count"] == 1
    assert metrics["combat_round_count"] >= 1
    assert metrics["causal_event_count"] >= 2
    assert metrics["dangling_cause_event_ids"] == []
