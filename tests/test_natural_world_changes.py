from __future__ import annotations

from fantasy_simulator.observation import (
    build_era_timeline_projection,
    build_location_history_projection,
    build_route_status_projection,
    build_war_map_projection,
)
from fantasy_simulator.content.setting_bundle import FactionRelationshipDefinition
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.reports import generate_yearly_report
from fantasy_simulator.simulation.world_change_driver import (
    generate_civilization_world_change,
    generate_era_world_change,
    generate_world_change,
    generate_occupation_world_change,
    generate_rename_world_change,
    generate_route_world_change,
    generate_terrain_world_change,
    generate_war_world_change,
)
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.ui.map_renderer import build_map_info
from fantasy_simulator.ui.view_models import build_monthly_report_card_view, build_world_dashboard_view
from fantasy_simulator.world import World


class FirstChoiceRng:
    def choice(self, values):
        return list(values)[0]

    def random(self) -> float:
        return 0.0


class OccupationThenRouteRng:
    def choice(self, values):
        choices = list(values)
        for choice in choices:
            name = getattr(choice, "__name__", "")
            if name == "generate_occupation_world_change":
                return choice
        for choice in choices:
            name = getattr(choice, "__name__", "")
            if name == "generate_route_world_change":
                return choice
        return choices[0]

    def random(self) -> float:
        return 0.0


def test_natural_route_world_change_is_visible_in_reports_and_map() -> None:
    sim = Simulator(World(), events_per_year=0, adventure_steps_per_year=0, world_changes_per_year=0, seed=12)

    record = generate_route_world_change(sim.world, month=1, day=1, rng=sim.rng)

    assert record is not None
    route_id = record.render_params["route_id"]
    from_location_id = record.render_params["from_location_id"]
    to_location_id = record.render_params["to_location_id"]

    projection = build_route_status_projection(
        routes=sim.world.routes,
        event_records=sim.world.event_records,
        route_id=route_id,
    )
    report = generate_yearly_report(sim.world, record.year)
    map_info = build_map_info(sim.world)
    from_cell = next(cell for cell in map_info.cells.values() if cell.location_id == from_location_id)
    to_cell = next(cell for cell in map_info.cells.values() if cell.location_id == to_location_id)

    assert projection.history[0].record_id == record.record_id
    assert [(entry.record_id, entry.category) for entry in report.world_change_entries] == [
        (record.record_id, "route")
    ]
    assert from_cell.recent_world_change_count == 1
    assert to_cell.recent_world_change_count == 1
    assert len(sim.world.rumors) == 1
    assert sim.world.rumors[0].tracked is True
    assert sim.world.rumors[0].source_event_id == record.record_id
    assert sim.world.rumors[0].related_location_ids == [from_location_id, to_location_id]

    card = build_monthly_report_card_view(sim.world, record.year, record.month)
    assert [(thread.source_event_id, thread.rumor_count) for thread in card.rumor_threads] == [
        (record.record_id, 1)
    ]


def test_natural_terrain_world_change_is_location_linked_and_reported() -> None:
    sim = Simulator(World(), events_per_year=0, adventure_steps_per_year=0, world_changes_per_year=0, seed=21)

    record = generate_terrain_world_change(sim.world, month=1, day=1, rng=sim.rng)

    assert record is not None
    location_id = record.render_params["location_id"]
    report = generate_yearly_report(sim.world, record.year)
    map_info = build_map_info(sim.world)
    cell = next(cell for cell in map_info.cells.values() if cell.location_id == location_id)

    assert record.kind == "terrain_cell_mutated"
    assert [(entry.record_id, entry.category) for entry in report.world_change_entries] == [
        (record.record_id, "terrain")
    ]
    assert cell.recent_world_change_count == 1
    assert cell.recent_world_change_categories == ("terrain",)


def test_natural_civilization_world_change_is_reported_without_location_overlay() -> None:
    sim = Simulator(World(), events_per_year=0, adventure_steps_per_year=0, world_changes_per_year=0, seed=22)

    record = generate_civilization_world_change(sim.world, month=1, day=1, rng=sim.rng)

    assert record is not None
    report = generate_yearly_report(sim.world, record.year)
    map_info = build_map_info(sim.world)

    assert record.kind == "civilization_phase_drifted"
    assert [(entry.record_id, entry.category) for entry in report.world_change_entries] == [
        (record.record_id, "civilization")
    ]
    assert all(cell.recent_world_change_count == 0 for cell in map_info.cells.values())


def test_natural_era_world_change_projects_reports_dashboards_and_roundtrips(tmp_path) -> None:
    world = World()
    rng = FirstChoiceRng()

    record = generate_era_world_change(world, month=2, day=3, rng=rng)

    assert record is not None
    projection = build_era_timeline_projection(event_records=world.event_records)
    report = generate_yearly_report(world, record.year)
    dashboard = build_world_dashboard_view(world, current_month=2)

    assert record.kind == "era_shifted"
    assert record.render_params["old_era_key"] == "age_of_embers"
    assert record.render_params["new_era_key"] == "age_of_bloom"
    assert projection.current_era_id == "age_of_bloom"
    assert projection.current_civilization_phase == "new_era"
    assert [(entry.record_id, entry.category) for entry in report.world_change_entries] == [
        (record.record_id, "era")
    ]
    assert dashboard.era_status is not None
    assert dashboard.era_status.era_id == "age_of_bloom"
    assert [entry.record_id for entry in dashboard.world_change_entries] == [record.record_id]

    path = tmp_path / "natural-era.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True
    restored = load_simulation(str(path))

    assert restored is not None
    restored_projection = build_era_timeline_projection(event_records=restored.world.event_records)
    restored_dashboard = build_world_dashboard_view(restored.world, current_month=2)
    assert restored_projection.current_era_id == "age_of_bloom"
    assert restored_dashboard.era_status is not None
    assert restored_dashboard.era_status.era_id == "age_of_bloom"


def test_natural_era_world_change_respects_minimum_interval() -> None:
    world = World()
    rng = FirstChoiceRng()

    first = generate_era_world_change(world, month=2, day=3, rng=rng)
    second = generate_era_world_change(world, month=3, day=4, rng=rng)
    world.year += 25
    third = generate_era_world_change(world, month=4, day=5, rng=rng)

    assert first is not None
    assert second is None
    assert third is not None


def test_natural_war_world_change_declares_active_war_visible_in_dashboard_report_and_map() -> None:
    world = World()
    rng = FirstChoiceRng()

    record = generate_war_world_change(world, month=2, day=3, rng=rng)

    assert record is not None
    projection = build_war_map_projection(event_records=world.event_records)
    report = generate_yearly_report(world, record.year)
    dashboard = build_world_dashboard_view(world, current_month=2)
    map_info = build_map_info(world)
    affected_cell = next(
        cell for cell in map_info.cells.values()
        if cell.location_id in record.render_params["location_ids"]
    )

    assert record.kind == "war_declared"
    assert projection.active_wars[0].record_id == record.record_id
    assert [(entry.record_id, entry.category) for entry in report.world_change_entries] == [
        (record.record_id, "war")
    ]
    assert [item.record_id for item in dashboard.active_wars] == [record.record_id]
    assert affected_cell.recent_world_change_categories == ("war",)


def test_natural_war_world_change_can_end_active_war_and_clear_dashboard() -> None:
    world = World()
    rng = FirstChoiceRng()
    declared = generate_war_world_change(world, month=2, day=3, rng=rng)

    ended = generate_war_world_change(world, month=4, day=5, rng=rng)

    assert declared is not None
    assert ended is not None
    projection = build_war_map_projection(event_records=world.event_records)
    dashboard = build_world_dashboard_view(world, current_month=4)
    report = generate_yearly_report(world, ended.year)

    assert [record.kind for record in world.event_records] == ["war_declared", "war_ended"]
    assert projection.active_wars == ()
    assert dashboard.active_wars == []
    assert [(entry.record_id, entry.category) for entry in report.world_change_entries] == [
        (declared.record_id, "war"),
        (ended.record_id, "war"),
    ]


def test_natural_occupation_world_change_uses_active_war_and_roundtrips(tmp_path) -> None:
    world = World()
    rng = FirstChoiceRng()
    declared = generate_war_world_change(world, month=2, day=3, rng=rng)

    occupied = generate_occupation_world_change(world, month=3, day=4, rng=rng)

    assert declared is not None
    assert occupied is not None
    projection = build_war_map_projection(event_records=world.event_records)
    report = generate_yearly_report(world, occupied.year)
    map_info = build_map_info(world)
    location_id = occupied.render_params["location_id"]
    cell = next(cell for cell in map_info.cells.values() if cell.location_id == location_id)

    assert occupied.kind == "location_faction_changed"
    assert occupied.render_params["new_faction_id"] in declared.render_params["belligerent_faction_ids"]
    assert projection.current_occupations[0].record_id == occupied.record_id
    assert [(entry.record_id, entry.category) for entry in report.world_change_entries] == [
        (declared.record_id, "war"),
        (occupied.record_id, "occupation"),
    ]
    assert cell.recent_world_change_categories == ("war", "occupation")

    path = tmp_path / "natural-occupation.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True
    restored = load_simulation(str(path))

    assert restored is not None
    restored_projection = build_war_map_projection(event_records=restored.world.event_records)
    assert [entry.record_id for entry in restored_projection.current_occupations] == [occupied.record_id]


def test_natural_occupation_world_change_uses_authored_initial_war() -> None:
    world = World()
    bundle = world.setting_bundle
    bundle.world_definition.faction_relationships = [
        FactionRelationshipDefinition(
            faction_a_id="stormwatch_wardens",
            faction_b_id="silverbrook_merchant_league",
            status="war",
            location_ids=["loc_silverbrook"],
        )
    ]
    world.apply_setting_bundle(bundle)
    rng = FirstChoiceRng()

    occupied = generate_occupation_world_change(world, month=3, day=4, rng=rng)

    assert occupied is not None
    projection = build_war_map_projection(
        event_records=world.event_records,
        faction_relationships=world.setting_bundle.world_definition.faction_relationships,
    )
    dashboard = build_world_dashboard_view(world, current_month=3)

    assert occupied.kind == "location_faction_changed"
    assert occupied.render_params["location_id"] == "loc_silverbrook"
    assert projection.active_wars[0].record_id.startswith("bundle:faction_relationship:")
    assert projection.current_occupations[0].record_id == occupied.record_id
    assert dashboard.active_wars[0].record_id.startswith("bundle:faction_relationship:")
    assert dashboard.current_occupations[0].record_id == occupied.record_id


def test_natural_rename_world_change_updates_history_report_map_and_save(tmp_path) -> None:
    world = World()
    rng = FirstChoiceRng()
    expected_location = next(
        location
        for location_id in sorted(world.location_ids)
        for location in [world.get_location_by_id(location_id)]
        if location is not None and location.controlling_faction_id
    )
    seed = next(
        site_seed
        for site_seed in world.setting_bundle.world_definition.site_seeds
        if site_seed.location_id == expected_location.id
    )
    expected_language_names = {
        world.language_engine.generate_toponym(
            seed.language_key,
            seed_key=(
                f"rename:{expected_location.id}:{expected_location.canonical_name}:"
                f"{expected_location.controlling_faction_id}:{index}"
            ),
            region_type=seed.region_type,
        )
        for index in range(4)
    }

    record = generate_rename_world_change(world, month=5, day=6, rng=rng)

    assert record is not None
    location_id = record.render_params["location_id"]
    location = world.get_location_by_id(location_id)
    assert location is not None
    projection = build_location_history_projection(
        locations=world.grid.values(),
        event_records=world.event_records,
        location_id=location_id,
    )
    report = generate_yearly_report(world, record.year)
    map_info = build_map_info(world)
    cell = next(cell for cell in map_info.cells.values() if cell.location_id == location_id)

    assert record.kind == "location_renamed"
    assert location_id == expected_location.id
    assert location.canonical_name == record.render_params["new_name"]
    assert record.render_params["new_name"] in expected_language_names
    assert projection.rename_history[0].record_id == record.record_id
    assert projection.aliases == (record.render_params["old_name"],)
    assert [(entry.record_id, entry.category) for entry in report.world_change_entries] == [
        (record.record_id, "location")
    ]
    assert cell.recent_world_change_categories == ("location",)

    path = tmp_path / "natural-rename.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True
    restored = load_simulation(str(path))

    assert restored is not None
    restored_location = restored.world.get_location_by_id(location_id)
    assert restored_location is not None
    assert restored_location.canonical_name == record.render_params["new_name"]
    assert restored_location.aliases == [record.render_params["old_name"]]


def test_configured_simulation_generates_a_natural_world_change() -> None:
    sim = Simulator(World(), events_per_year=0, adventure_steps_per_year=0, world_changes_per_year=360, seed=12)

    sim.advance_days(1)

    assert len(sim.world.event_records) == 1
    assert "world_change" in sim.world.event_records[0].tags


def test_configured_natural_world_change_surfaces_pending_notification() -> None:
    sim = Simulator(World(), events_per_year=0, adventure_steps_per_year=0, world_changes_per_year=360, seed=12)

    sim.advance_days(1)

    assert [record.record_id for record in sim.pending_notifications] == [
        sim.world.event_records[0].record_id
    ]


def test_auto_advance_pauses_for_natural_world_change_notification() -> None:
    sim = Simulator(World(), events_per_year=0, adventure_steps_per_year=0, world_changes_per_year=360, seed=12)

    result = sim.advance_until_pause(max_years=1)

    assert result["pause_reason"] == "world_change_notification"
    assert result["days_advanced"] == 1
    assert result["pause_subreasons"][0]["key"] == "world_change_notification"
    assert result["recommended_actions"][0]["key"] == "review_world_dashboard"
    assert len(sim.pending_notifications) == 1
    assert sim.pending_notifications[0].record_id == sim.world.event_records[0].record_id


def test_natural_world_change_generation_falls_back_after_noop_generator() -> None:
    world = World()
    rng = OccupationThenRouteRng()

    record = generate_world_change(world, month=1, day=1, rng=rng)

    assert record is not None
    assert record.kind == "route_blocked"
    assert [stored.record_id for stored in world.event_records] == [record.record_id]


def test_natural_world_change_budget_roundtrips_through_save_load(tmp_path) -> None:
    sim = Simulator(World(), events_per_year=0, adventure_steps_per_year=0, world_changes_per_year=360, seed=13)
    sim.advance_days(1)
    path = tmp_path / "natural-world-change.json"

    assert save_simulation(sim, str(path)) is True
    restored = load_simulation(str(path))

    assert restored is not None
    assert restored.world_changes_per_year == 360
    assert [record.to_dict() for record in restored.world.event_records] == [
        record.to_dict() for record in sim.world.event_records
    ]
