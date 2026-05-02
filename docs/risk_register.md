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
- Locale-aware event rendering contract.
  Status: completed in the current branch worktree.
  Evidence: `event_log` and reports render canonical records through
  `summary_key`/`render_params`; `render_params` rejects non-JSON values and
  keeps faction absence as semantic `null` until display time.
- World-change event quality.
  Status: completed in the current branch worktree.
  Evidence: world-change APIs no-op without appending records when the state is
  unchanged, fail fast rather than storing empty fallback descriptions, and
  roll back state when canonical recording fails.
- Route visibility adapter coverage.
  Status: completed in the current branch worktree.
  Evidence: route block/reopen records carry endpoint IDs and `location:*` tags
  so reports and location queries include both connected sites.

## Remaining Risks

- Canonical event records drift from legacy adapters.
  Impact: reports, summaries, and UI event logs disagree after load.
  Guardrail: `world.event_records` remains canonical; current-schema conflict
  tests reject stale `event_log` precedence; display adapters render canonical
  records through the shared event renderer; route visibility uses endpoint IDs
  and `location:*` tags rather than display text.
- Locale-aware rendering coverage remains partial for legacy simulation events.
  Impact: world-change events can be re-rendered from `summary_key` and
  `render_params`, while older battle/meeting-style records may continue to
  display their stored compatibility description.
  Guardrail: strict event rendering detects broken summary metadata; future
  migrations should add semantic params to ordinary event families explicitly.
- Language runtime cache diverges from durable history.
  Impact: generated names and endonyms change depending on save shape.
  Guardrail: `language_evolution_history` wins over
  `language_runtime_states`; language docs and tests cover replay.
- Documentation trails code-level contract changes.
  Impact: agents make incompatible changes because the source of truth is
  unclear.
  Guardrail: `tests/test_doc_freshness.py` checks this contract and risk
  register for key precedence terms.
- Hydration precedence changes without regression tests.
  Impact: unchanged save schemas still load differently because canonical
  records, legacy adapters, or derived caches are reconciled in a new order.
  Guardrail: behavior-only hydration changes require focused save/load
  conflict tests even when `CURRENT_VERSION` stays unchanged; schema-version
  bumps still require migration tests and README/agent doc freshness updates.

## Current Status

- No open blocker for Step 6/9 documentation and conflict-precedence coverage.
- Save schema format was not changed for this step; hydration guardrails and
  derived-cache rebuild behavior were tightened.
- RR-001 route graph is no longer tracked as an open serialization risk.
- Remaining future risk is additive: new PR-K dynamic world state fields must
  declare their canonical source and conflict behavior before persistence lands.
