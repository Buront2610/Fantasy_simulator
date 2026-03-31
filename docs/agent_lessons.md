# Agent Lessons

Keep this file curated. Add only lessons that are likely to recur.

## Recurrent Pitfalls

- `flake8 .` is noisy because `.claude/worktrees/` may contain unrelated files.
  Prefer targeted lint paths or `python scripts/quality_gate.py strict`.
- `event_log` and `history` are compatibility layers, not new read-paths.
- Full-text narrative snapshots become expensive quickly; prefer projections.

## Repo-Specific Constraints

- `docs/implementation_plan.md` is roadmap authority.
- `docs/architecture.md` is guardrail authority.
- Advance roadmap work with well-bounded subagents when possible.
- Let subagents hand off bounded follow-up review/implementation work, but keep the same plan anchor and progress text in sync.
- Keep roadmap / status text synchronized with actual progress in the same change.
- Save/load compatibility matters; avoid format changes unless explicitly requested.
- User-facing strings must go through i18n helpers.

## Useful Verification Moves

- Narrow change: `python scripts/quality_gate.py minimal --pytest-target ...`
- Guardrail-heavy change: `python scripts/quality_gate.py standard`
- Cross-cutting change: `python scripts/quality_gate.py strict`
