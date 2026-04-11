# Verifier Role

## Purpose
Run repository quality gates with a profile selected from changed areas.

## Output Shape
- `verification_profile`: `minimal` / `standard` / `strict`
- `verification_commands`: executable command list
- `verification_result`: overall status
- `command_results`: per-command return code and status

## Guardrails
- Prefer `scripts/quality_gate.py` as the primary verification entry point.
- Keep command execution argument-based (`argv`) and avoid shell-string execution.
- Record failures as structured data in the run manifest.
