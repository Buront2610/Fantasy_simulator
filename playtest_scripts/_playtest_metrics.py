# Playtest harness: run long simulations and measure balance/bug claims empirically.
import statistics
from collections import Counter

from fantasy_simulator.world import World
from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.simulation.engine import Simulator


def build_sim(seed, n_chars=20):
    world = World()
    creator = CharacterCreator()
    for _ in range(n_chars):
        world.add_character(creator.create_random())
    return Simulator(world, seed=seed)


def all_chars(world):
    chars = getattr(world, "characters", None)
    if isinstance(chars, dict):
        return list(chars.values())
    return list(chars)


def run_one(seed, years=100, n_chars=20):
    sim = build_sim(seed, n_chars)
    sim.advance_years(years)
    world = sim.world
    chars = all_chars(world)
    alive = [c for c in chars if getattr(c, "alive", True)]
    dead = [c for c in chars if not getattr(c, "alive", True)]

    # 1. Relationship saturation
    rel_scores = []
    for c in alive:
        rel_scores.extend(c.relationships.values())
    sat_hi = sum(1 for s in rel_scores if s >= 95)
    sat_lo = sum(1 for s in rel_scores if s <= -95)

    # 2. Stranded survivors (active_adventure_id pointing to non-active run)
    active_ids = {r.adventure_id for r in world.active_adventures}
    stranded = [
        c for c in alive
        if getattr(c, "active_adventure_id", None) and c.active_adventure_id not in active_ids
    ]

    # 3. Adventures
    n_completed = len(world.completed_adventures)
    n_active = len(world.active_adventures)
    outcomes = Counter(getattr(r, "outcome", None) for r in world.completed_adventures)

    # 4. Elder stat collapse (long-lived races in long middle band)
    elders = [c for c in alive if c.age >= 80]
    elder_profile = [
        (c.race, c.age, c.wisdom, c.dexterity, c.strength)
        for c in sorted(elders, key=lambda c: -c.age)[:6]
    ]

    # 5. Stat extremes among alive
    dex1 = sum(1 for c in alive if c.dexterity <= 2)
    wis100 = sum(1 for c in alive if c.wisdom >= 99)

    # 6. Skill levels (do they grow? are they capped?)
    skill_lvls = [v for c in alive for v in c.skills.values()]

    # 7. Injury distribution
    inj = Counter(getattr(c, "injury_status", "none") for c in alive)

    return {
        "seed": seed,
        "alive": len(alive),
        "dead": len(dead),
        "rel_n": len(rel_scores),
        "rel_mean": round(statistics.mean(rel_scores), 1) if rel_scores else None,
        "rel_sat_hi": sat_hi,
        "rel_sat_lo": sat_lo,
        "stranded": len(stranded),
        "stranded_names": [(c.name, c.age) for c in stranded][:5],
        "adv_completed": n_completed,
        "adv_active": n_active,
        "adv_outcomes": dict(outcomes),
        "elders": elder_profile,
        "dex<=2": dex1,
        "wis>=99": wis100,
        "skill_max": max(skill_lvls) if skill_lvls else None,
        "skill_mean": round(statistics.mean(skill_lvls), 2) if skill_lvls else None,
        "injury": dict(inj),
    }


if __name__ == "__main__":
    for seed in (7, 42, 1234):
        r = run_one(seed, years=100, n_chars=20)
        print(f"=== seed={r['seed']}  100y, start pop 20 ===")
        print(f"  alive={r['alive']} dead={r['dead']}")
        print(f"  relationships: n={r['rel_n']} mean={r['rel_mean']} "
              f">=+95: {r['rel_sat_hi']}  <=-95: {r['rel_sat_lo']}")
        print(f"  adventures: completed={r['adv_completed']} active={r['adv_active']} "
              f"outcomes={r['adv_outcomes']}")
        print(f"  STRANDED survivors (dangling active_adventure_id): {r['stranded']} {r['stranded_names']}")
        print(f"  elders(age>=80, top6): {r['elders']}")
        print(f"  stat extremes: dex<=2: {r['dex<=2']}  wis>=99: {r['wis>=99']}")
        print(f"  skills: max={r['skill_max']} mean={r['skill_mean']}")
        print(f"  injury: {r['injury']}")
        print()
