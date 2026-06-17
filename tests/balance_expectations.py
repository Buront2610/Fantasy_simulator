"""Health-band expectations for simulation balance smoke tests."""

WORLD_HEALTH_SEEDS = (7, 42)
WORLD_HEALTH_YEARS = 30
WORLD_HEALTH_STARTING_POPULATION = 20

# These are not "perfect balance" claims. They are executable tripwires for the
# review_report_2026-06-10 findings: extinction, marriage starvation, and
# tragedy-free adventures should not silently return. Combat bands catch the
# §12 regression where battles fall back to single-roll, flavor-only logs.
MIN_ALIVE_AFTER_HEALTH_RUN = 10
MIN_TOTAL_MARRIAGES = 1
MIN_TOTAL_IMMIGRATIONS = 1
MIN_TOTAL_ADVENTURE_DEATHS = 1
MIN_TOTAL_COMBAT_EVENTS = 10
MIN_TOTAL_COMBAT_ROUNDS = 30
MIN_TOTAL_MAGIC_COMBAT_ACTIONS = 1
