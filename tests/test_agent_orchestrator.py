from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.agent_orchestrator import (
    AgentOrchestrator,
    OrchestratorInput,
    build_verification_commands,
    route_verification_profile,
)


class RecordingRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> int:
        self.commands.append(list(command))
        return 0


def _load_manifest(runs_root: Path, task_id: str) -> dict:
    path = runs_root / task_id / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_orchestrator_runs_roles_in_expected_order(tmp_path: Path) -> None:
    orchestrator = AgentOrchestrator(command_runner=RecordingRunner(), runs_root=tmp_path)

    manifest = orchestrator.run(
        OrchestratorInput(
            task_id='test-order',
            goal='Validate role ordering',
            changed_files=['docs/architecture.md'],
            consulted_design_texts=['docs/architecture.md'],
            canonical_source_notes=['Architecture sync checked'],
        )
    )

    assert manifest['roles_run'] == ['planner', 'implementer', 'verifier', 'reviewer']


def test_follow_up_keeps_same_plan_anchor_when_reviewer_blocks(tmp_path: Path) -> None:
    orchestrator = AgentOrchestrator(command_runner=RecordingRunner(), runs_root=tmp_path)

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
    assert route_verification_profile(['docs/architecture.md']) == 'standard'
    assert route_verification_profile(['tests/test_events.py']) == 'minimal'
    assert route_verification_profile(['fantasy_simulator/simulation/engine.py']) == 'strict'
    assert route_verification_profile(['fantasy_simulator/persistence/migrations.py']) == 'strict'
    assert route_verification_profile(['scripts/agent_orchestrator.py']) == 'standard'


def test_manifest_contains_required_fields(tmp_path: Path) -> None:
    orchestrator = AgentOrchestrator(command_runner=RecordingRunner(), runs_root=tmp_path)

    task_id = 'test-required-fields'
    orchestrator.run(
        OrchestratorInput(
            task_id=task_id,
            goal='Check required manifest fields',
            changed_files=['tests/test_agent_orchestrator.py'],
        )
    )
    manifest = _load_manifest(tmp_path, task_id)

    required_keys = {
        'task_id',
        'created_at',
        'goal',
        'plan_anchor',
        'changed_area',
        'roles_run',
        'verification_profile',
        'verification_commands',
        'verification_command_results',
        'result',
        'follow_up_needed',
        'follow_up_reason',
        'docs_sync_required',
        'docs_sync_status',
        'consulted_design_texts',
        'narrative_docs_revalidated',
        'canonical_source_affected',
        'canonical_source_notes',
    }
    assert required_keys.issubset(manifest.keys())


def test_dry_run_does_not_execute_verification_commands(tmp_path: Path) -> None:
    runner = RecordingRunner()
    orchestrator = AgentOrchestrator(command_runner=runner, runs_root=tmp_path)

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


def test_docs_sync_status_is_recorded(tmp_path: Path) -> None:
    orchestrator = AgentOrchestrator(command_runner=RecordingRunner(), runs_root=tmp_path)

    manifest = orchestrator.run(
        OrchestratorInput(
            task_id='test-docs-sync',
            goal='Record docs sync state',
            changed_files=['docs/implementation_plan.md'],
            docs_sync_status='confirmed',
            consulted_design_texts=['docs/implementation_plan.md'],
            canonical_source_notes=['Plan sync checked'],
        )
    )

    assert manifest['docs_sync_required'] is True
    assert manifest['docs_sync_status'] == 'confirmed'


def test_profile_routing_representative_areas() -> None:
    assert route_verification_profile(['fantasy_simulator/persistence/save_load.py']) == 'strict'
    assert route_verification_profile(['fantasy_simulator/simulation/timeline.py']) == 'strict'
    assert route_verification_profile(['fantasy_simulator/narrative/context.py']) == 'strict'
    assert route_verification_profile(['fantasy_simulator/ui/map_renderer.py']) == 'strict'
    assert route_verification_profile(['docs/agent_roles/planner.md']) == 'minimal'


def test_minimal_docs_role_changes_include_agent_workflow_docs_target() -> None:
    commands = build_verification_commands("minimal", ["docs/agent_roles/planner.md"])
    argv = commands[0]
    assert "tests/test_doc_freshness.py" in argv
    assert "tests/test_agent_workflow_docs.py" in argv


def test_semantic_audit_fields_are_explicit_inputs(tmp_path: Path) -> None:
    orchestrator = AgentOrchestrator(command_runner=RecordingRunner(), runs_root=tmp_path)
    manifest = orchestrator.run(
        OrchestratorInput(
            task_id="semantic-audit",
            goal="Record explicit semantic audit data",
            changed_files=["scripts/agent_orchestrator.py"],
            consulted_design_texts=["docs/implementation_plan.md"],
            narrative_docs_revalidated=["docs/contexts/review.md"],
            canonical_source_affected=True,
            canonical_source_notes=["World.event_records contract reviewed"],
        )
    )
    assert manifest["consulted_design_texts"] == ["docs/implementation_plan.md"]
    assert manifest["narrative_docs_revalidated"] == ["docs/contexts/review.md"]
    assert manifest["canonical_source_affected"] is True
    assert manifest["canonical_source_notes"] == ["World.event_records contract reviewed"]


def test_semantic_audit_is_required_for_high_impact_changes(tmp_path: Path) -> None:
    orchestrator = AgentOrchestrator(command_runner=RecordingRunner(), runs_root=tmp_path)
    with pytest.raises(ValueError, match="Semantic audit required"):
        orchestrator.run(
            OrchestratorInput(
                task_id="missing-audit",
                goal="Update architecture guardrails",
                changed_files=["docs/architecture.md"],
            )
        )


def test_narrative_changes_require_narrative_revalidation(tmp_path: Path) -> None:
    orchestrator = AgentOrchestrator(command_runner=RecordingRunner(), runs_root=tmp_path)
    with pytest.raises(ValueError, match="Narrative changes require"):
        orchestrator.run(
            OrchestratorInput(
                task_id="narrative-audit",
                goal="Update narrative context rules",
                changed_files=["fantasy_simulator/narrative/context.py"],
                consulted_design_texts=["docs/implementation_plan.md"],
                canonical_source_notes=["Narrative contract reviewed"],
            )
        )


def test_orchestrator_writes_manifests_to_custom_root_only(tmp_path: Path) -> None:
    task_id = "isolated-output"
    orchestrator = AgentOrchestrator(command_runner=RecordingRunner(), runs_root=tmp_path)
    orchestrator.run(
        OrchestratorInput(
            task_id=task_id,
            goal="Use isolated manifest root",
            changed_files=["tests/test_agent_orchestrator.py"],
        )
    )

    assert (tmp_path / task_id / "manifest.json").exists()
    assert not (Path(".runs") / task_id / "manifest.json").exists()
