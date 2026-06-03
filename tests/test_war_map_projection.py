from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.observation import build_war_map_projection
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.reports import format_monthly_report, generate_monthly_report
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.ui.map_renderer import build_map_info, render_region_map
from fantasy_simulator.world import World
from fantasy_simulator.world_change.event_contracts import validate_world_change_event_contract


def test_war_map_projection_reads_war_and_occupation_records_without_world_runtime() -> None:
    records = [
        WorldEventRecord(
            record_id="rec_war",
            kind="war_declared",
            year=12,
            month=2,
            day=1,
            description="War was declared.",
            render_params={
                "location_id": "loc_aethoria_capital",
                "belligerent_faction_ids": ["wardens", "dawn_court"],
            },
        ),
        WorldEventRecord(
            record_id="rec_occupied",
            kind="location_faction_changed",
            year=12,
            month=2,
            day=3,
            location_id="loc_silverbrook",
            description="Silverbrook changed hands.",
            render_params={
                "location_id": "loc_silverbrook",
                "old_faction_id": None,
                "new_faction_id": "wardens",
            },
        ),
        WorldEventRecord(
            record_id="rec_liberated",
            kind="occupation_ended",
            year=12,
            month=4,
            day=5,
            description="Silverbrook was liberated.",
            render_params={
                "location_id": "loc_silverbrook",
                "old_faction_id": "wardens",
            },
        ),
    ]

    projection = build_war_map_projection(event_records=records)

    assert [entry.record_id for entry in projection.events] == [
        "rec_war",
        "rec_occupied",
        "rec_liberated",
    ]
    assert projection.active_wars[0].faction_ids == ("dawn_court", "wardens")
    assert projection.affected_location_ids == ("loc_aethoria_capital", "loc_silverbrook")
    assert projection.faction_ids == ("wardens", "dawn_court")
    assert [(entry.location_id, entry.status) for entry in projection.occupation_history] == [
        ("loc_silverbrook", "occupied"),
        ("loc_silverbrook", "unoccupied"),
    ]
    assert projection.current_occupations == ()


def test_war_map_projection_derives_occupation_from_location_impact() -> None:
    record = WorldEventRecord(
        record_id="rec_impact_occupation",
        kind="location_occupied",
        year=4,
        month=6,
        day=7,
        description="The ford was occupied.",
        impacts=[
            {
                "target_type": "location",
                "target_id": "loc_ford",
                "attribute": "controlling_faction_id",
                "old_value": "ford_keepers",
                "new_value": "river_host",
            }
        ],
    )

    projection = build_war_map_projection(event_records=[record])

    assert projection.current_occupations[0].location_id == "loc_ford"
    assert projection.current_occupations[0].previous_faction_id == "ford_keepers"
    assert projection.current_occupations[0].controlling_faction_id == "river_host"


def test_world_war_declaration_records_project_and_report() -> None:
    previous_locale = get_locale()
    set_locale("en")
    world = World()

    try:
        record = world.apply_war_declaration(
            "stormwatch_wardens",
            "silverbrook_merchant_league",
            location_ids=("loc_aethoria_capital", "loc_silverbrook"),
            year=1001,
            month=6,
            day=7,
            cause_key="border_incident",
        )

        validate_world_change_event_contract(record)
        assert record.kind == "war_declared"
        assert record.summary_key == "events.war_declared.summary"
        assert record.severity == 4
        assert record.render_params["belligerent_faction_ids"] == [
            "stormwatch_wardens",
            "silverbrook_merchant_league",
        ]
        assert "war" in record.tags
        assert "faction:stormwatch_wardens" in record.tags
        assert "location:loc_silverbrook" in record.tags

        projection = build_war_map_projection(event_records=world.event_records)
        assert projection.events[0].record_id == record.record_id
        assert projection.events[0].faction_ids == ("stormwatch_wardens", "silverbrook_merchant_league")
        assert projection.active_wars[0].record_id == record.record_id
        assert projection.affected_location_ids == ("loc_aethoria_capital", "loc_silverbrook")

        report = generate_monthly_report(world, 1001, 6)
        assert [(entry.record_id, entry.category) for entry in report.world_change_entries] == [
            (record.record_id, "war")
        ]
        text = format_monthly_report(report)
        assert "▶ World Changes" in text
        assert "War:" in text
        assert "Stormwatch Wardens declared war on Silverbrook Merchant League." in text
    finally:
        set_locale(previous_locale)


def test_world_war_ending_closes_active_war_and_roundtrips(tmp_path) -> None:
    previous_locale = get_locale()
    set_locale("en")
    world = World()
    capital = world.get_location_by_id("loc_aethoria_capital")
    silverbrook = world.get_location_by_id("loc_silverbrook")
    assert capital is not None
    assert silverbrook is not None

    try:
        declared = world.apply_war_declaration(
            "stormwatch_wardens",
            "silverbrook_merchant_league",
            location_ids=("loc_aethoria_capital", "loc_silverbrook"),
            year=1001,
            month=6,
            day=7,
        )
        before_end = (capital.danger, capital.rumor_heat, capital.safety, capital.mood)
        ended = world.apply_war_ended(
            "silverbrook_merchant_league",
            "stormwatch_wardens",
            location_ids=("loc_silverbrook", "loc_aethoria_capital"),
            year=1001,
            month=8,
            day=2,
            cause_key="truce",
        )

        validate_world_change_event_contract(ended)
        assert ended.kind == "war_ended"
        assert ended.summary_key == "events.war_ended.summary"
        assert ended.render_params["belligerent_faction_ids"] == [
            "silverbrook_merchant_league",
            "stormwatch_wardens",
        ]
        assert "Silverbrook Merchant League ended war with Stormwatch Wardens." in ended.description
        assert (capital.danger, capital.rumor_heat, capital.safety, capital.mood) == (
            max(0, before_end[0] - 8),
            min(100, before_end[1] + 12),
            min(100, before_end[2] + 6),
            min(100, before_end[3] + 8),
        )
        assert capital.live_traces[-1]["text"].startswith(
            "Silverbrook Merchant League ended war with Stormwatch Wardens."
        )

        projection = build_war_map_projection(event_records=world.event_records)
        assert [entry.record_id for entry in projection.events] == [declared.record_id, ended.record_id]
        assert projection.active_wars == ()

        report = generate_monthly_report(world, 1001, 8)
        assert [(entry.record_id, entry.category) for entry in report.world_change_entries] == [
            (ended.record_id, "war")
        ]
        info = build_map_info(world)
        capital_cell = next(cell for cell in info.cells.values() if cell.location_id == "loc_aethoria_capital")
        assert capital_cell.recent_world_change_categories == ("war",)

        path = tmp_path / "war-ended-roundtrip.json"
        assert save_simulation(Simulator(world, seed=0), str(path)) is True
        restored = load_simulation(str(path))

        assert restored is not None
        restored_projection = build_war_map_projection(event_records=restored.world.event_records)
        assert [entry.kind for entry in restored_projection.events] == ["war_declared", "war_ended"]
        assert restored_projection.active_wars == ()
    finally:
        set_locale(previous_locale)


def test_war_declaration_applies_location_state_pressure_and_map_visibility() -> None:
    previous_locale = get_locale()
    set_locale("en")
    world = World()
    capital = world.get_location_by_id("loc_aethoria_capital")
    silverbrook = world.get_location_by_id("loc_silverbrook")
    assert capital is not None
    assert silverbrook is not None
    before_capital = (capital.danger, capital.rumor_heat, capital.safety, capital.mood)
    before_silverbrook = (silverbrook.danger, silverbrook.rumor_heat, silverbrook.safety, silverbrook.mood)

    try:
        record = world.apply_war_declaration(
            "stormwatch_wardens",
            "silverbrook_merchant_league",
            location_ids=("loc_aethoria_capital", "loc_silverbrook"),
            year=1001,
            month=6,
            day=7,
        )

        assert (capital.danger, capital.rumor_heat, capital.safety, capital.mood) == (
            min(100, before_capital[0] + 15),
            min(100, before_capital[1] + 25),
            max(0, before_capital[2] - 10),
            max(0, before_capital[3] - 10),
        )
        assert (silverbrook.danger, silverbrook.rumor_heat, silverbrook.safety, silverbrook.mood) == (
            min(100, before_silverbrook[0] + 15),
            min(100, before_silverbrook[1] + 25),
            max(0, before_silverbrook[2] - 10),
            max(0, before_silverbrook[3] - 10),
        )
        assert capital.live_traces[-1]["text"].startswith(
            "Stormwatch Wardens declared war on Silverbrook Merchant League."
        )
        assert silverbrook.live_traces[-1]["text"] == capital.live_traces[-1]["text"]

        info = build_map_info(world)
        capital_cell = next(cell for cell in info.cells.values() if cell.location_id == "loc_aethoria_capital")
        assert capital_cell.recent_world_change_count == 1
        assert capital_cell.recent_world_change_categories == ("war",)
        rendered = render_region_map(info, "loc_aethoria_capital", radius=2)
        assert "World change: Aethoria Capital changed recently (War)" in rendered
        assert record.record_id in capital.recent_event_ids
    finally:
        set_locale(previous_locale)
