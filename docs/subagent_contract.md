# Subagent Contract

Use this contract when delegating focused work to a subagent.

## Required Inputs

- `Goal`: the concrete question or task
- `Why`: the larger purpose behind the task
- `Plan anchor`: the roadmap item, checklist entry, or text section that must stay accurate
- `Allowed scope`: files, modules, or read-only boundaries
- `Forbidden scope`: files or actions the subagent must not touch
- `Expected output`: the exact shape of the answer you want back

## Recommended Output Shapes

### Research

- Facts with file references
- Open questions
- Suggested next step

### Plan

- Proposed approach
- Risks or assumptions
- Verification plan

### Implement

- Files changed
- Behavior changed
- Verification performed
- Text or plan sections that must be synchronized with the progress

### Review

- Findings only, ordered by severity
- File references
- Residual risk if no findings

## Rules

- Pass objective context, not only the surface query.
- Ask for evidence, not confidence language.
- Prefer one well-bounded task per subagent.
- Avoid overlapping write scopes across subagents.
- When the task advances a roadmap item, update the linked plan text in the same change.
- Keep public/status text synchronized with actual progress; do not leave stale checklist or roadmap wording behind.
- If the result is incomplete, send a follow-up question before accepting it.
