from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.observation import build_location_history_projection
from fantasy_simulator.ui.map_renderer import build_map_info
from fantasy_simulator.world import World
from fantasy_simulator.world_location_state import clamp_state


def test_location_history_projection_reports_current_name_without_history() -> None:
    world = World()
    location = world.get_location_by_id("loc_aethoria_capital")
    assert location is not None

    projection = build_location_history_projection(
        locations=world.grid.values(),
        event_records=world.event_records,
        location_id=location.id,
    )

    assert projection.location_id == location.id
    assert projection.official_name == "Aethoria Capital"
    assert projection.aliases == ()
    assert projection.rename_history == ()


def test_location_history_projection_includes_rename_history() -> None:
    world = World()

    first = world.apply_location_rename_change("loc_aethoria_capital", "Aethoria March", month=2, day=3)
    second = world.apply_location_rename_change("loc_aethoria_capital", "Marchhold", month=4, day=5)

    projection = build_location_history_projection(
        locations=world.grid.values(),
        event_records=world.event_records,
        location_id="loc_aethoria_capital",
    )

    assert first is not None
    assert second is not None
    assert projection.official_name == "Marchhold"
    assert projection.aliases == ("Aethoria Capital", "Aethoria March")
    assert [entry.record_id for entry in projection.rename_history] == [first.record_id, second.record_id]
    assert [(entry.old_name, entry.new_name) for entry in projection.rename_history] == [
        ("Aethoria Capital", "Aethoria March"),
        ("Aethoria March", "Marchhold"),
    ]
    assert [entry.day for entry in projection.rename_history] == [3, 5]
    assert all(record_id in projection.recent_event_ids for record_id in [first.record_id, second.record_id])


def test_location_rename_applies_location_state_pressure_and_map_visibility() -> None:
    previous_locale = get_locale()
    set_locale("en")
    world = World()
    location = world.get_location_by_id("loc_aethoria_capital")
    assert location is not None
    before = (location.rumor_heat, location.traffic, location.mood)

    try:
        record = world.apply_location_rename_change("loc_aethoria_capital", "Aethoria March", month=2, day=3)
    finally:
        set_locale(previous_locale)

    assert record is not None
    assert (location.rumor_heat, location.traffic, location.mood) == (
        clamp_state(before[0] + 12),
        clamp_state(before[1] + 4),
        clamp_state(before[2] + 2),
    )
    assert location.live_traces[-1]["char_name"] == "world"
    assert "new name" in location.live_traces[-1]["text"]

    map_info = build_map_info(world)
    cell = next(cell for cell in map_info.cells.values() if cell.location_id == "loc_aethoria_capital")
    assert cell.traffic_indicator == location.traffic_indicator
    assert cell.mood == location.mood


def test_location_history_projection_filters_other_locations() -> None:
    world = World()

    capital_record = world.apply_location_rename_change("loc_aethoria_capital", "Aethoria March")
    harbor_record = world.apply_location_rename_change("loc_silverbrook", "Silver Haven")

    projection = build_location_history_projection(
        locations=world.grid.values(),
        event_records=world.event_records,
        location_id="loc_aethoria_capital",
    )

    assert capital_record is not None
    assert harbor_record is not None
    assert [entry.record_id for entry in projection.rename_history] == [capital_record.record_id]
    assert harbor_record.record_id not in [entry.record_id for entry in projection.rename_history]


def test_location_history_projection_reads_rename_names_from_impacts() -> None:
    world = World()
    record = WorldEventRecord(
        record_id="rec_sparse_rename",
        kind="location_renamed",
        year=world.year,
        month=8,
        day=9,
        location_id="loc_aethoria_capital",
        description="Sparse rename.",
        impacts=[
            {
                "target_type": "location",
                "target_id": "loc_aethoria_capital",
                "attribute": "canonical_name",
                "old_value": "Aethoria Capital",
                "new_value": "Aethoria March",
            }
        ],
    )

    projection = build_location_history_projection(
        locations=world.grid.values(),
        event_records=[record],
        location_id="loc_aethoria_capital",
    )

    assert [(entry.old_name, entry.new_name) for entry in projection.rename_history] == [
        ("Aethoria Capital", "Aethoria March"),
    ]


def test_location_history_projection_includes_control_history() -> None:
    world = World()

    first = world.apply_controlling_faction_change(
        "loc_aethoria_capital",
        "stormwatch_wardens",
        month=2,
        day=3,
    )
    second = world.apply_controlling_faction_change("loc_aethoria_capital", None, month=3, day=4)

    projection = build_location_history_projection(
        locations=world.grid.values(),
        event_records=world.event_records,
        location_id="loc_aethoria_capital",
    )

    assert first is not None
    assert second is not None
    assert [entry.record_id for entry in projection.control_history] == [first.record_id, second.record_id]
    assert [(entry.old_faction_id, entry.new_faction_id) for entry in projection.control_history] == [
        (None, "stormwatch_wardens"),
        ("stormwatch_wardens", None),
    ]
