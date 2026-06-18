"""Tests for the deterministic seeded simulation stats helper."""

from __future__ import annotations

import json

from scripts.simulation_stats import collect_simulation_stats, format_stats, main


def test_collect_simulation_stats_is_deterministic() -> None:
    first = collect_simulation_stats(years=1, months=2)
    second = collect_simulation_stats(years=1, months=2)

    assert first == second
    assert first.years == 1
    assert first.months == 2
    assert first.total_months == 14
    assert first.events >= 0
    assert first.rumors >= 0
    assert 0 <= first.alive <= first.characters
    assert len(first.population_series) == 3
    assert first.population_series[0].elapsed_months == 0
    assert first.population_series[-1].elapsed_months == 14
    assert first.population_series[-1].by_location


def test_format_stats_includes_required_counters() -> None:
    stats = collect_simulation_stats(years=0, months=1, characters=3)
    text = format_stats(stats)

    assert "events: " in text
    assert "rumors: " in text
    assert "alive: " in text
    assert "years: 0" in text
    assert "months: 1" in text
    assert "population_series:" in text
    assert "locations=[" in text


def test_main_prints_deterministic_json(capsys) -> None:
    exit_code = main(["--years", "0", "--months", "1", "--characters", "3", "--format", "json"])

    assert exit_code == 0
    data = json.loads(capsys.readouterr().out)
    assert data["years"] == 0
    assert data["months"] == 1
    assert data["characters"] == 3
    assert set(data) >= {"events", "rumors", "alive", "total_months"}
    assert data["population_series"][0]["elapsed_months"] == 0
    assert data["population_series"][-1]["elapsed_months"] == 1
    assert isinstance(data["population_series"][-1]["by_location"], dict)
