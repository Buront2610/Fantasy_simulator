from __future__ import annotations

import json
from pathlib import Path

from scripts.agent_orchestrator import AgentOrchestrator, OrchestratorInput, route_verification_profile


class RecordingRunner:
    def __init__(self) -> None:
        self.commands: list[str] = []

    def __call__(self, command: str) -> int:
        self.commands.append(command)
        return 0


def _load_manifest(task_id: str) -> dict:
    path = Path('.runs') / task_id / 'manifest.json'
    return json.loads(path.read_text(encoding='utf-8'))


def test_orchestrator_runs_roles_in_expected_order() -> None:
    orchestrator = AgentOrchestrator(command_runner=RecordingRunner())

    manifest = orchestrator.run(
        OrchestratorInput(
            task_id='test-order',
            goal='Validate role ordering',
            changed_files=['docs/architecture.md'],
        )
    )

    assert manifest['roles_run'] == ['planner', 'implementer', 'verifier', 'reviewer']


def test_follow_up_keeps_same_plan_anchor_when_reviewer_blocks() -> None:
    orchestrator = AgentOrchestrator(command_runner=RecordingRunner())

    manifest = orchestrator.run(
        OrchestratorInput(
            task_id='test-follow-up',
            goal='Trigger blocker [review:blocker]',
            plan_anchor='anchor-pr-i-loop',
            changed_files=['scripts/agent_orchestrator.py'],
        )
    )

    assert manifest['follow_up_needed'] is True
    assert manifest['follow_up_task']['plan_anchor'] == 'anchor-pr-i-loop'


def test_verification_profile_routing_cases() -> None:
    assert route_verification_profile(['docs/architecture.md']) == 'minimal'
    assert route_verification_profile(['tests/test_events.py']) == 'minimal'
    assert route_verification_profile(['fantasy_simulator/simulation/engine.py']) == 'strict'
    assert route_verification_profile(['fantasy_simulator/persistence/migrations.py']) == 'strict'
    assert route_verification_profile(['scripts/agent_orchestrator.py']) == 'standard'


def test_manifest_contains_required_fields() -> None:
    orchestrator = AgentOrchestrator(command_runner=RecordingRunner())

    task_id = 'test-required-fields'
    orchestrator.run(
        OrchestratorInput(
            task_id=task_id,
            goal='Check required manifest fields',
            changed_files=['tests/test_agent_orchestrator.py'],
        )
    )
    manifest = _load_manifest(task_id)

    required_keys = {
        'task_id',
        'created_at',
        'goal',
        'plan_anchor',
        'changed_area',
        'roles_run',
        'verification_profile',
        'verification_commands',
        'result',
        'follow_up_needed',
        'follow_up_reason',
        'docs_sync_required',
        'docs_sync_status',
    }
    assert required_keys.issubset(manifest.keys())


def test_dry_run_does_not_execute_verification_commands() -> None:
    runner = RecordingRunner()
    orchestrator = AgentOrchestrator(command_runner=runner)

    manifest = orchestrator.run(
        OrchestratorInput(
            task_id='test-dry-run',
            goal='Dry run should avoid execution',
            changed_files=['scripts/agent_orchestrator.py'],
        ),
        dry_run=True,
    )

    assert runner.commands == []
    assert manifest['verification_result'] == 'skipped'
    assert manifest['dry_run'] is True


def test_docs_sync_status_is_recorded() -> None:
    orchestrator = AgentOrchestrator(command_runner=RecordingRunner())

    manifest = orchestrator.run(
        OrchestratorInput(
            task_id='test-docs-sync',
            goal='Record docs sync state',
            changed_files=['docs/implementation_plan.md'],
            docs_sync_status='confirmed',
        )
    )

    assert manifest['docs_sync_required'] is True
    assert manifest['docs_sync_status'] == 'confirmed'


def test_profile_routing_representative_areas() -> None:
    assert route_verification_profile(['fantasy_simulator/persistence/save_load.py']) == 'strict'
    assert route_verification_profile(['fantasy_simulator/simulation/timeline.py']) == 'strict'
    assert route_verification_profile(['docs/agent_roles/planner.md']) == 'minimal'
