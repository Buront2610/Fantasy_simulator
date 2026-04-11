# Reviewer Role

## Purpose
Review with a **clean context** so findings do not inherit implementer assumptions.

## Output Shape
- `findings`: ordered by severity (high -> medium -> low)
- `residual_risk`: concise risk summary after review
- `smallest_follow_up_task`: minimal bounded next task when needed

## Blocker Rule
If a blocker exists, return a smallest follow-up implementation/research task that keeps the same plan anchor.
