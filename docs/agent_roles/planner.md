# Planner Role

## Purpose
Translate a single task into a bounded approach tied to one **plan anchor**.

## Output Shape
- `approach`: concise execution strategy
- `risks`: explicit risk list (scope, verification gaps, doc drift)
- `verification_plan`: concrete checks to run

## Guardrails
- Keep alignment with `docs/implementation_plan.md` as roadmap source of truth.
- Keep alignment with `docs/architecture.md` for current constraints.
- Prefer small incremental plans that can be reviewed independently.
