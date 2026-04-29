# Risk Register

This register tracks risks that are still relevant to the typed world contract
work and its serialization guardrails.

## Completed Guardrails

- RR-001 route graph contract.
  Status: completed in the current branch worktree.
  Evidence: explicit empty bundle route graphs remain disconnected after
  save/load; route adjacency is owned by `world_route_graph.py`; serialized
  topology rejects duplicate route IDs, duplicate route pairs, malformed route
  scalars, and route overlays whose endpoints disagree with the canonical
  graph.
- Serialization conflict precedence docs and tests.
  Status: completed for Step 6/9.
  Evidence: `docs/serialization_contract.md`, `tests/test_doc_freshness.py`,
  and focused save/load conflict tests cover event adapter precedence and
  language history/cache precedence.

## Remaining Risks

- Canonical event records drift from legacy adapters.
  Impact: reports, summaries, and UI event logs disagree after load.
  Guardrail: `world.event_records` remains canonical; current-schema conflict
  tests reject stale `event_log` precedence.
- Language runtime cache diverges from durable history.
  Impact: generated names and endonyms change depending on save shape.
  Guardrail: `language_evolution_history` wins over
  `language_runtime_states`; language docs and tests cover replay.
- Documentation trails code-level contract changes.
  Impact: agents make incompatible changes because the source of truth is
  unclear.
  Guardrail: `tests/test_doc_freshness.py` checks this contract and risk
  register for key precedence terms.
- Save schema changes without migration tests.
  Impact: old snapshots fail or hydrate with partial defaults.
  Guardrail: `CURRENT_VERSION` bumps require migration tests and
  README/agent doc freshness updates.

## Current Status

- No open blocker for Step 6/9 documentation and conflict-precedence coverage.
- Core serialization logic was not changed for this step.
- RR-001 route graph is no longer tracked as an open serialization risk.
- Remaining future risk is additive: new PR-K dynamic world state fields must
  declare their canonical source and conflict behavior before persistence lands.
