# ADR 0004: Sparse Terrain Mutation Persistence Uses Canonical Records

Status: Accepted for issue #74
Date: 2026-05-04

## Context

Schema v8 already keeps bundle-backed terrain compact by omitting
`world.terrain_map` when the runtime grid still matches terrain derived from the
active setting bundle. Before this ADR, any terrain mutation made bundle terrain
look non-derived, so save output fell back to a complete terrain snapshot. That
made one-cell changes scale with world size.

PR-K world-change APIs now record terrain cell changes as canonical
`WorldEventRecord` entries of kind `terrain_cell_mutated`. Those records contain
the cell coordinate and old/new values for biome, elevation, moisture, and
temperature.

## Decision

Bundle-backed terrain uses canonical terrain-cell mutation records as the sparse
overlay.

Save policy:

- Derive the active bundle terrain.
- If runtime terrain equals derived terrain, omit `world.terrain_map`.
- Otherwise, replay canonical `terrain_cell_mutated` records over derived
  terrain.
- If replay equals runtime terrain, omit `world.terrain_map`.
- If replay cannot be validated or does not match runtime terrain, emit the
  existing full `world.terrain_map` snapshot.

Load policy:

- If a bundle-backed save includes `world.terrain_map`, validate and apply the
  full snapshot. This preserves v8 compatibility and gives explicit snapshots
  precedence over event replay.
- If a bundle-backed save omits `world.terrain_map`, derive terrain from the
  bundle and replay canonical terrain-cell mutation records in event order.
- Non-bundle or incompatible-grid saves continue to require explicit topology
  snapshots for mutated terrain.

This introduces no new save field. The sparse path is an interpretation of the
existing canonical event record contract.

## Consequences

- Single-cell PR-K terrain mutations stay proportional to the event record, not
  to map size.
- Direct runtime edits to `TerrainCell` still save full snapshots because they
  have no durable canonical mutation record.
- Full v8 `terrain_map` snapshots remain loadable and win when present.
- Bad or stale sparse terrain records fail load for snapshotless bundle-backed
  saves, because they are the durable overlay in that path.

## Fitness Functions / Tests

- A `World.apply_terrain_cell_change()` round trip preserves runtime terrain and
  canonical history without saving `world.terrain_map`.
- Direct terrain cell edits still emit `world.terrain_map`.
- A save containing both canonical terrain records and a full `world.terrain_map`
  loads the full snapshot.
- Strict quality gate remains green.
