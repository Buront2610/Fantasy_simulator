# Implementer Role

## Purpose
Execute bounded changes for one task without widening scope.

## Output Shape
- `files_changed`: concrete file list
- `behavior_changed`: user/system-visible effects
- `verification_run`: checks executed by implementer

## Guardrails
- Preserve canonical `World.event_records` usage.
- Do not break save/load compatibility.
- Respect architecture dependency boundaries.
