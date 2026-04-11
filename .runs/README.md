# Run Manifests

`.runs/<task-id>/manifest.json` stores machine-readable orchestration outcomes.

Required manifest fields include:
- task/goal metadata (`task_id`, `created_at`, `goal`, `plan_anchor`)
- execution metadata (`roles_run`, `verification_profile`, `verification_commands`)
- outcome metadata (`result`, `follow_up_needed`, `follow_up_reason`)
- docs sync metadata (`docs_sync_required`, `docs_sync_status`)
- lessons hook (`repeated_failure_key`, `suggested_lesson`, `suggested_test_or_guardrail`)

Artifacts under `.runs/` are local workflow traces and can be cleaned between sessions.
