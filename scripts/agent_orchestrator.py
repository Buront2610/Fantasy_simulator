"""Minimal agent orchestration loop for repo-local role-based workflows.

This module intentionally focuses on a local, testable contract:
planner -> implementer -> verifier -> reviewer.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = REPO_ROOT / ".runs"


@dataclass(frozen=True)
class PlannerOutput:
    approach: str
    risks: list[str]
    verification_plan: list[str]


@dataclass(frozen=True)
class ImplementerOutput:
    files_changed: list[str]
    behavior_changed: list[str]
    verification_run: list[str]


@dataclass(frozen=True)
class ReviewFinding:
    severity: str
    summary: str


@dataclass(frozen=True)
class ReviewerOutput:
    findings: list[ReviewFinding]
    residual_risk: str
    smallest_follow_up_task: str | None
    blocker: bool = False


@dataclass(frozen=True)
class FollowUpTask:
    task_id: str
    goal: str
    plan_anchor: str
    reason: str


@dataclass(frozen=True)
class OrchestratorInput:
    goal: str
    task_id: str | None = None
    plan_anchor: str | None = None
    changed_files: list[str] = field(default_factory=list)
    target_area: str | None = None
    docs_sync_status: str = "pending"


class RoleAdapter:
    """Adapter for role execution.

    This is intentionally abstracted so local stubs can be replaced by real agents
    later without changing manifest contracts.
    """

    def run_planner(self, task: OrchestratorInput, plan_anchor: str) -> PlannerOutput:
        raise NotImplementedError

    def run_implementer(self, task: OrchestratorInput, plan_anchor: str, planner: PlannerOutput) -> ImplementerOutput:
        raise NotImplementedError

    def run_reviewer(
        self,
        task: OrchestratorInput,
        plan_anchor: str,
        planner: PlannerOutput,
        implementer: ImplementerOutput,
    ) -> ReviewerOutput:
        raise NotImplementedError


class StubRoleAdapter(RoleAdapter):
    """Deterministic local adapter used for minimal executable orchestration."""

    def run_planner(self, task: OrchestratorInput, plan_anchor: str) -> PlannerOutput:
        return PlannerOutput(
            approach=f"Use small, reversible changes for {plan_anchor}.",
            risks=["Under-scoped verification", "Doc sync drift"],
            verification_plan=["Route profile", "Run quality gate", "Review clean-context findings"],
        )

    def run_implementer(self, task: OrchestratorInput, plan_anchor: str, planner: PlannerOutput) -> ImplementerOutput:
        files = task.changed_files or ([task.target_area] if task.target_area else [])
        behavior = [f"Prepared implementation steps for {plan_anchor}"]
        return ImplementerOutput(
            files_changed=[item for item in files if item],
            behavior_changed=behavior,
            verification_run=[],
        )

    def run_reviewer(
        self,
        task: OrchestratorInput,
        plan_anchor: str,
        planner: PlannerOutput,
        implementer: ImplementerOutput,
    ) -> ReviewerOutput:
        blocker = "[review:blocker]" in task.goal
        finding = ReviewFinding(
            severity="high" if blocker else "low",
            summary=(
                "Blocker: additional bounded implementation is required."
                if blocker
                else "No blocker detected in clean-context review."
            ),
        )
        return ReviewerOutput(
            findings=[finding],
            residual_risk="medium" if blocker else "low",
            smallest_follow_up_task=(
                "Investigate reviewer blocker and submit bounded patch"
                if blocker
                else None
            ),
            blocker=blocker,
        )


def resolve_plan_anchor(goal: str, provided_anchor: str | None = None) -> str:
    if provided_anchor:
        return provided_anchor
    slug = re.sub(r"[^a-z0-9]+", "-", goal.lower()).strip("-")
    slug = slug[:24] or "task"
    return f"anchor-{slug}"


def route_verification_profile(changed_files: Sequence[str], target_area: str | None = None) -> str:
    areas = set(changed_files)
    if target_area:
        areas.add(target_area)

    if not areas:
        return "standard"

    docs_only = all(path.startswith("docs/") or path.endswith(".md") for path in areas)
    tests_only = all(path.startswith("tests/") for path in areas)

    if any("persistence/" in path for path in areas):
        return "strict"
    if any("simulation/" in path for path in areas):
        return "strict"
    if docs_only:
        return "minimal"
    if tests_only:
        return "minimal"
    if any(path.startswith("docs/architecture") or path.startswith("docs/implementation_plan") for path in areas):
        return "standard"
    return "standard"


def build_verification_commands(profile: str, changed_files: Sequence[str]) -> list[str]:
    changed_tests = [path for path in changed_files if path.startswith("tests/")]
    command = [sys.executable, "scripts/quality_gate.py", profile]
    if profile == "minimal" and changed_tests:
        for test_path in changed_tests:
            command.extend(["--pytest-target", test_path])
    elif profile == "minimal":
        command.extend(["--pytest-target", "tests/test_quality_gate.py"])
    return [" ".join(command)]


def docs_sync_required(changed_files: Sequence[str]) -> bool:
    return any(path.startswith("docs/") or path.startswith("scripts/") for path in changed_files)


def _default_command_runner(command: str) -> int:
    return subprocess.run(command, cwd=REPO_ROOT, shell=True, check=False).returncode


class AgentOrchestrator:
    def __init__(
        self,
        adapter: RoleAdapter | None = None,
        command_runner: Callable[[str], int] | None = None,
    ) -> None:
        self.adapter = adapter or StubRoleAdapter()
        self.command_runner = command_runner or _default_command_runner

    def run(self, task: OrchestratorInput, dry_run: bool = False) -> dict:
        task_id = task.task_id or f"task-{uuid4().hex[:8]}"
        plan_anchor = resolve_plan_anchor(task.goal, task.plan_anchor)

        planner = self.adapter.run_planner(task, plan_anchor)
        implementer = self.adapter.run_implementer(task, plan_anchor, planner)

        changed_area = implementer.files_changed or list(task.changed_files)
        profile = route_verification_profile(changed_area, task.target_area)
        verification_commands = build_verification_commands(profile, changed_area)

        verification_result = "skipped"
        if not dry_run:
            verification_result = "passed"
            for command in verification_commands:
                rc = self.command_runner(command)
                if rc != 0:
                    verification_result = "failed"
                    break

        reviewer = self.adapter.run_reviewer(task, plan_anchor, planner, implementer)

        follow_up_needed = reviewer.blocker
        follow_up_reason = reviewer.smallest_follow_up_task or ""
        follow_up_task = None
        if follow_up_needed and follow_up_reason:
            follow_up_task = asdict(
                FollowUpTask(
                    task_id=f"{task_id}-follow-up",
                    goal=follow_up_reason,
                    plan_anchor=plan_anchor,
                    reason="reviewer_blocker",
                )
            )

        manifest = {
            "task_id": task_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "goal": task.goal,
            "plan_anchor": plan_anchor,
            "changed_area": changed_area,
            "target_area": task.target_area,
            "roles_run": ["planner", "implementer", "verifier", "reviewer"],
            "role_outputs": {
                "planner": asdict(planner),
                "implementer": asdict(implementer),
                "reviewer": {
                    "findings": [asdict(item) for item in reviewer.findings],
                    "residual_risk": reviewer.residual_risk,
                    "smallest_follow_up_task": reviewer.smallest_follow_up_task,
                    "blocker": reviewer.blocker,
                },
            },
            "verification_profile": profile,
            "verification_commands": verification_commands,
            "verification_result": verification_result,
            "result": "blocked" if follow_up_needed else ("failed" if verification_result == "failed" else "completed"),
            "follow_up_needed": follow_up_needed,
            "follow_up_reason": follow_up_reason,
            "follow_up_task": follow_up_task,
            "docs_sync_required": docs_sync_required(changed_area),
            "docs_sync_status": task.docs_sync_status,
            "repeated_failure_key": "reviewer_blocker" if follow_up_needed else "",
            "suggested_lesson": follow_up_reason if follow_up_needed else "",
            "suggested_test_or_guardrail": (
                "Add focused regression test for blocker path"
                if follow_up_needed
                else ""
            ),
            "dry_run": dry_run,
        }
        self._write_manifest(task_id, manifest)
        return manifest

    def _write_manifest(self, task_id: str, manifest: dict) -> None:
        run_dir = RUNS_ROOT / task_id
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / "manifest.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("goal", help="Task goal description")
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--plan-anchor", default=None)
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--target-area", default=None)
    parser.add_argument("--docs-sync-status", default="pending")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    task = OrchestratorInput(
        goal=args.goal,
        task_id=args.task_id,
        plan_anchor=args.plan_anchor,
        changed_files=args.changed_file,
        target_area=args.target_area,
        docs_sync_status=args.docs_sync_status,
    )
    orchestrator = AgentOrchestrator()
    manifest = orchestrator.run(task, dry_run=args.dry_run)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
