from __future__ import annotations

from fantasy_simulator.adventure import AdventureRun
from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.rumor_models import Rumor
from fantasy_simulator.world import World
from fantasy_simulator.world_history_retention import compact_world_history


def test_history_retention_keeps_required_events_and_prunes_old_noise() -> None:
    world = World()
    world.year = 1100
    location = world.get_location_by_id("loc_aethoria_capital")
    assert location is not None

    noise = [
        WorldEventRecord(record_id=f"old_noise_{index}", kind="meeting", year=1000, severity=1)
        for index in range(8)
    ]
    cause = WorldEventRecord(record_id="old_cause", kind="meeting", year=1000, severity=1)
    marriage = WorldEventRecord(
        record_id="old_marriage",
        kind="marriage",
        year=1001,
        severity=4,
        cause_event_ids=[cause.record_id],
    )
    recent = WorldEventRecord(record_id="recent_training", kind="skill_training", year=1098, severity=1)
    world.event_records = [*noise, cause, marriage, recent]
    location.recent_event_ids = [noise[0].record_id, recent.record_id]

    compact_world_history(world, max_event_records=3, recent_years=5, max_rumor_archive=10)

    retained_ids = {record.record_id for record in world.event_records}
    assert marriage.record_id in retained_ids
    assert cause.record_id in retained_ids
    assert recent.record_id in retained_ids
    assert noise[0].record_id in retained_ids
    assert retained_ids.isdisjoint({record.record_id for record in noise[1:]})
    assert location.recent_event_ids == [noise[0].record_id, recent.record_id]
    assert world._event_index.record_ids == retained_ids


def test_history_retention_keeps_world_arc_related_events_even_when_old() -> None:
    world = World()
    world.year = 1200
    declared = world.apply_war_declaration(
        "stormwatch_wardens",
        "silverbrook_merchant_league",
        location_ids=("loc_aethoria_capital", "loc_silverbrook"),
        year=1000,
    )
    old_noise = [
        WorldEventRecord(record_id=f"old_noise_{index}", kind="meeting", year=1000, severity=1)
        for index in range(8)
    ]
    world.event_records = old_noise + world.event_records

    compact_world_history(world, max_event_records=2, recent_years=5, max_rumor_archive=10)

    assert declared.record_id in {record.record_id for record in world.event_records}


def test_history_retention_keeps_rumor_event_references_even_when_old() -> None:
    world = World()
    world.year = 1200
    source = WorldEventRecord(record_id="old_rumor_source", kind="meeting", year=1000, severity=1)
    related = WorldEventRecord(record_id="old_rumor_related", kind="meeting", year=1000, severity=1)
    archived_source = WorldEventRecord(record_id="old_archived_source", kind="meeting", year=1000, severity=1)
    noise = [
        WorldEventRecord(record_id=f"old_noise_{index}", kind="meeting", year=1000, severity=1)
        for index in range(8)
    ]
    world.event_records = [*noise, source, related, archived_source]
    world.rumors = [
        Rumor(
            id="tracked-rumor",
            source_event_id=source.record_id,
            related_event_ids=[related.record_id],
            tracked=True,
        )
    ]
    world.rumor_archive = [
        Rumor(id="archived-rumor", source_event_id=archived_source.record_id, tracked=True)
    ]

    compact_world_history(world, max_event_records=1, recent_years=5, max_rumor_archive=10)

    assert world.get_event_by_id(source.record_id) is not None
    assert world.get_event_by_id(related.record_id) is not None
    assert world.get_event_by_id(archived_source.record_id) is not None


def test_history_retention_bounds_rumor_archive_and_prefers_tracked_recent_rumors() -> None:
    world = World()
    world.rumor_archive = [
        Rumor(id="old", year_created=1000, created_absolute_day=1, tracked=False),
        Rumor(id="tracked", year_created=1000, created_absolute_day=2, tracked=True),
        Rumor(id="recent", year_created=1100, created_absolute_day=3, tracked=False),
        Rumor(id="newest", year_created=1101, created_absolute_day=4, tracked=False),
    ]

    compact_world_history(world, max_event_records=10, recent_years=5, max_rumor_archive=2)

    assert [rumor.id for rumor in world.rumor_archive] == ["tracked", "newest"]


def test_completed_adventure_retention_prunes_old_runs_and_old_event_references() -> None:
    world = World()
    world.year = 1300
    old_runs = [
        AdventureRun(
            character_id=f"char_{index}",
            character_name=f"Hero {index}",
            origin="loc_aethoria_capital",
            destination="loc_silverbrook",
            year_started=1000 + index,
            adventure_id=f"old_{index}",
            state="resolved",
            outcome="safe_return",
            resolution_year=1000 + index,
            summary_log=[f"summary {step}" for step in range(30)],
            detail_log=[f"detail {step}" for step in range(30)],
            related_event_ids=[f"old_event_{index}_{step}" for step in range(10)],
            combat_logs=[{"combat_log": [{"round_number": step}]} for step in range(5)],
        )
        for index in range(6)
    ]
    recent_death = AdventureRun(
        character_id="char_recent",
        character_name="Recent Hero",
        origin="loc_aethoria_capital",
        destination="loc_silverbrook",
        year_started=1298,
        adventure_id="recent_death",
        state="resolved",
        outcome="death",
        resolution_year=1299,
        related_event_ids=["recent_event"],
    )
    world.completed_adventures = [*old_runs, recent_death]
    world.event_records = [
        WorldEventRecord(record_id=f"old_event_{index}_{step}", kind="adventure_step", year=1000, severity=1)
        for index in range(6)
        for step in range(10)
    ] + [
        WorldEventRecord(record_id="recent_event", kind="adventure_death", year=1299, severity=5),
        WorldEventRecord(record_id="recent_noise", kind="meeting", year=1299, severity=1),
    ]

    compact_world_history(
        world,
        max_event_records=12,
        recent_years=5,
        max_rumor_archive=10,
        max_completed_adventures=3,
        completed_adventure_recent_years=20,
    )

    assert len(world.completed_adventures) == 3
    assert "recent_death" in {run.adventure_id for run in world.completed_adventures}
    for run in world.completed_adventures:
        if run.adventure_id.startswith("old_"):
            assert len(run.summary_log) == 12
            assert len(run.detail_log) == 12
            assert len(run.related_event_ids) == 4
            assert len(run.combat_logs) == 2
    retained_event_ids = {record.record_id for record in world.event_records}
    assert "recent_event" in retained_event_ids
    assert len(retained_event_ids) <= 12
