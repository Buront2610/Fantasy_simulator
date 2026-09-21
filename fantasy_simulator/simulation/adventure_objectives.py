"""Select concrete goals from witnessed injuries or reachable circulating reports."""

from typing import Any

from ..adventure.objective import AdventureObjective, default_objective
from ..i18n import tr


def _report_reaches(world: Any, origin: str, source: str, spread: int) -> bool:
    frontier, seen = {source}, {source}
    for _ in range(spread + 1):
        if origin in frontier:
            return True
        frontier = {loc.id for site in frontier for loc in world.get_travel_neighboring_locations(site)} - seen
        seen.update(frontier)
    return False


def _received_injury_reports(world: Any, leader: Any) -> dict[str, str]:
    """Trace reports to canonical events and require a passable dissemination path."""
    # ID lookups validate mutation-sensitive signatures of the whole history. Capture
    # fresh references once per decision instead of rescanning it for every rumor.
    records = {record.record_id: record for record in world.event_records}
    reports = {}
    for rumor in world.rumors:
        event = records.get(rumor.source_event_id)
        if (rumor.is_expired or event is None or not rumor.source_location_id
                or event.kind not in ("adventure_injured", "condition_worsened", "battle")):
            continue
        if _report_reaches(world, leader.location_id, rumor.source_location_id, rumor.spread_level):
            for actor_id in (event.primary_actor_id, *event.secondary_actor_ids):
                reports[actor_id] = event.record_id
    return reports


def known_rescue_targets(world: Any, leader: Any) -> list[tuple[Any, str | None]]:
    """Find witnessed/reported casualties for which this actor is willing to depart."""
    reports = _received_injury_reports(world, leader)
    assigned = {run.objective.target_id for run in world.active_adventures
                if run.objective is not None and run.objective.purpose == "rescue"
                and run.objective.status in ("active", "rescued")}
    targets = []
    for actor in world.characters:
        place = world.character_presence_location_id(actor)
        if actor.char_id == leader.char_id or not actor.alive or actor.injury_status not in ("serious", "dying"):
            continue
        owner = world.get_adventure_by_id(actor.active_adventure_id) if actor.active_adventure_id else None
        if owner and owner.objective and owner.objective.purpose == "rescue":
            continue
        if actor.char_id in assigned or place is None or leader.get_relationship(actor.char_id) < -20:
            continue
        if place == leader.location_id or actor.char_id in reports:
            targets.append((actor, reports.get(actor.char_id)))
    return sorted(targets, key=lambda item: (-leader.get_relationship(item[0].char_id), item[0].char_id))


def prepare_objective(world: Any, run: Any, members: list[Any]) -> None:
    if run.objective is None:
        run.objective = default_objective(run.policy)
    if run.objective.purpose != "rescue":
        return
    target = world.get_character_by_id(run.objective.target_id)
    if target is None or not target.alive or target.char_id in run.member_ids:
        raise ValueError("Rescue requires a live target outside the rescuing party")
    location_id = world.character_presence_location_id(target)
    if location_id is None or target.injury_status not in ("serious", "dying"):
        raise ValueError("Rescue target is not stationary and in need of rescue")
    run.objective.source_adventure_id = target.active_adventure_id
    run.destination = location_id
    run.danger_level = world.get_location_by_id(location_id).danger
    text = tr("adventure.rescue_departure", name=run.character_name, target=target.name,
              location=world.location_name(location_id))
    run.summary_log[:] = [text]
    run.detail_log.append(text)


def rescue_source_run(world: Any, run: Any) -> Any:
    goal = run.objective
    if goal is None or goal.purpose != "rescue" or goal.status != "active":
        return None
    target = world.get_character_by_id(goal.target_id)
    source = world.get_adventure_by_id(target.active_adventure_id) if target and target.active_adventure_id else None
    return source if source is not None and source.adventure_id != run.adventure_id else None


def objective_participants(world: Any, run: Any) -> list[Any]:
    goal = run.objective
    if goal is None or goal.purpose != "rescue":
        return []
    target = world.get_character_by_id(goal.target_id)
    if target is None:
        raise ValueError("Unknown rescue target")
    source = rescue_source_run(world, run)
    return [target, *([world.get_character_by_id(mid) for mid in source.member_ids] if source else [])]


def try_start_rescue(simulator: Any, candidates: list[Any]) -> bool:
    """One concrete emergency response per day, before the normal expedition lottery."""
    from ..adventure import AdventureRun, generate_adventure_id

    if not any(c.alive and c.injury_status in ("serious", "dying") for c in simulator.world.characters):
        return False
    for leader in sorted(candidates, key=lambda actor: (-actor.wisdom, actor.char_id)):
        targets = known_rescue_targets(simulator.world, leader)
        if not targets:
            continue
        reachable = {leader.location_id, *simulator.world.reachable_location_ids(leader.location_id)}
        for target, evidence in targets:
            if target.location_id not in reachable:
                continue
            members = [leader, *[actor for actor in candidates
                                 if actor.char_id != leader.char_id and actor.location_id == leader.location_id
                                 and actor.get_relationship(target.char_id) >= 0][:2]]
            run = AdventureRun(leader.char_id, leader.name, leader.location_id, target.location_id,
                               simulator.world.year, adventure_id=generate_adventure_id(simulator.id_rng),
                               member_ids=[member.char_id for member in members],
                               objective=AdventureObjective("rescue", "swift", target.char_id,
                                                            target.active_adventure_id, evidence))
            simulator._commit_adventure_start(run, members)
            return True
    return False
