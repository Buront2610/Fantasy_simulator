# Review Context

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
- Does it treat completed PR-K K0 guardrail slices as unstarted, full PR-K complete, or persistable without evidence/ADR?
- Does PR-K wording keep active mainline status separate from completed K0 slices?
- For world-change work, does the slice still follow the local K0 checklist in
  `docs/pr_k_prerequisite_design.md`?
- Is verification proportional to the scope of the change?
- If it blocks completion, what is the smallest follow-up subagent that should handle it?

## Useful Baselines

- `docs/implementation_plan.md`, `docs/architecture.md`, `tests/test_architecture_constraints.py`, `tests/test_doc_freshness.py`

## Review Output Shape

- Findings first, ordered by severity, with file references.
- Smallest follow-up implementation/research subagent when a blocker remains.
- Residual risk if there are no findings.
