# Measure what world changes actually happen over 100y with the UI's setting (1/year).
from collections import Counter

from fantasy_simulator.world import World
from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.simulation.engine import Simulator

for seed in (7, 42):
    world = World()
    creator = CharacterCreator()
    for _ in range(20):
        world.add_character(creator.create_random())
    sim = Simulator(world, events_per_year=8, world_changes_per_year=1, seed=seed)
    sim.advance_years(100)

    all_kinds = Counter(rec.kind for rec in world.event_records)
    wc_types = Counter()
    wars = []          # (year, kind)
    era_shifts = []
    for rec in world.event_records:
        et = rec.kind
        if any(token in et for token in ("war", "occupation", "renam", "terrain", "era",
                                         "civilization", "route")):
            wc_types[et] += 1
            if "war" in et:
                wars.append((rec.year, et))
            if "era" in et and "civil" not in et:
                era_shifts.append(rec.year)

    total_records = len(world.event_records)
    print(f"=== seed={seed} 100y, world_changes_per_year=1 ===")
    print(f"  total event records: {total_records}")
    print(f"  record kinds (top): {all_kinds.most_common(12)}")
    print(f"  world-change breakdown: {dict(wc_types)}")
    print(f"  era shift years: {era_shifts}")
    print(f"  war timeline: {wars}")
    # war durations
    open_war = None
    durations = []
    for year, kind in wars:
        if kind == "war_declared":
            open_war = year
        elif open_war is not None:
            durations.append(year - open_war)
            open_war = None
    print(f"  war durations (years): {durations}")
    print()
