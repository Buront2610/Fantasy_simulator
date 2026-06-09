# ADR 0005: Python Version Policy

## Status

Accepted.

## Context

The project currently declares Python 3.10+ in `pyproject.toml`, README, and
agent-facing setup docs. The focused mypy configuration also targets Python
3.10. PR-K work is expected to expand typed world-change commands, IDs,
projections, and persistence guardrails, so the supported interpreter baseline
must remain explicit while that work is active.

## Decision

Python 3.10 remains the minimum supported runtime for the PR-K mainline.

The project may raise the minimum only after all of the following are true:

- CI coverage for the proposed new minimum has been added or reviewed.
- README, AGENTS.md, CLAUDE.md, `pyproject.toml`, and mypy configuration are
  updated in the same change.
- A focused compatibility check confirms no supported save/load fixture or CLI
  entry point relies on the old minimum.
- The change is treated as platform policy, not as a side effect of a feature
  PR.

## Consequences

- PR-K typed-ID ratchet work should use Python 3.10-compatible typing syntax.
- New dependencies may be added when useful, but they must support the declared
  Python minimum.
- Quality-gate and doc-freshness tests remain the enforcement surface for
  keeping the declared baseline synchronized.
