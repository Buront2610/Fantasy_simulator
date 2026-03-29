# Implementation Context

Use this file when the task is primarily about changing code.

## Keep In Mind

- `docs/implementation_plan.md` is the roadmap source of truth.
- `docs/architecture.md` is the current guardrail summary.
- `World.event_records` is canonical; `event_log` and `history` are compatibility layers.
- Preserve save/load compatibility unless the task explicitly authorizes format changes.
- Prefer small, test-backed edits over broad refactors.

## Expected Workflow

1. Confirm the changed area and nearest relevant tests.
2. Make the smallest coherent patch that satisfies the task.
3. Run the narrowest useful verification first.
4. Escalate to broader verification if the change crosses boundaries.

## Default Verification

- Changed-area work: `python scripts/quality_gate.py minimal --pytest-target ...`
- Guardrail-sensitive work: `python scripts/quality_gate.py standard`
- Cross-cutting or release-sensitive work: `python scripts/quality_gate.py strict`

## Avoid

- Treating exploratory docs as roadmap authority.
- Spreading new reads of compatibility adapters.
- Adding user-facing strings without i18n coverage.
