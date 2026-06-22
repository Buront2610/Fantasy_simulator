# Track population / relationship trajectory decade by decade.
import statistics
from _playtest_metrics import build_sim, all_chars

for seed in (7, 42):
    sim = build_sim(seed, n_chars=20)
    print(f"=== seed={seed} ===")
    print("year  alive  rel_n  rel_mean  rel>=80  rel<=-80  marriages")
    for decade in range(10):
        sim.advance_years(10)
        chars = all_chars(sim.world)
        alive = [c for c in chars if c.alive]
        rels = [v for c in alive for v in c.relationships.values()]
        married = sum(1 for c in alive if getattr(c, "spouse_id", None))
        hi = sum(1 for v in rels if v >= 80)
        lo = sum(1 for v in rels if v <= -80)
        mean = round(statistics.mean(rels), 1) if rels else "-"
        print(f"{(decade+1)*10:>4}  {len(alive):>5}  {len(rels):>5}  {mean!s:>8}  {hi:>7}  {lo:>8}  {married:>9}")
    print()
