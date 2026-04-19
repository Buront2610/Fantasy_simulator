"""Generate a seeded worldgen PoC snapshot as JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fantasy_simulator.worldgen import WorldgenConfig, generate_world


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--height", type=int, default=18)
    parser.add_argument("--site-limit", type=int, default=12)
    parser.add_argument("--output", type=Path, default=Path("worldgen_preview.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    world = generate_world(
        WorldgenConfig(
            width=args.width,
            height=args.height,
            seed=args.seed,
            site_candidate_limit=args.site_limit,
        )
    )
    args.output.write_text(json.dumps(world.to_dict(), indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
