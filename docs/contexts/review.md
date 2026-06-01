# Review Context

Use this file when the task is primarily code review or risk assessment.

## Review Priorities

1. Behavioral regressions
2. Save/load and migration risks
3. Violations of architecture guardrails
4. Missing or mis-scoped verification
5. Brittleness that will slow future agent work

## What To Check

- Does the change add new reads from `event_log` or `history`?
- Does it bypass i18n rules for user-facing text?
- Does it introduce a layer dependency that the structural tests should forbid?
- Does it modify roadmap or guardrail docs without keeping them aligned?
- Does PR-K wording distinguish the active mainline milestone from the already
  merged K0 guardrail/contract slices?
- For world-change work, is the slice still inside the Command -> validation ->
  state machine -> domain event -> `WorldEventRecord` -> `ChangeSet` -> reducer
  -> projection/view model -> UI/report -> tests path?
- Is verification proportional to the scope of the change?
- If it blocks completion, what is the smallest follow-up subagent that should handle it?

## Useful Baselines

- `docs/implementation_plan.md`
- `docs/architecture.md`
- `tests/test_architecture_constraints.py`
- `tests/test_doc_freshness.py`
- `tests/test_harness_scenarios.py`
## Review Output Shape

- Findings first, ordered by severity
- File references for each finding
- Smallest follow-up implementation/research subagent when a blocker remains
- Residual risk if there are no findings
