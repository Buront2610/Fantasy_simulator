"""Profile-based verification runner for local agent workflows.

Usage examples
--------------
    python scripts/quality_gate.py minimal --pytest-target tests/test_character_creator.py
    python scripts/quality_gate.py standard
    python scripts/quality_gate.py playtest
    python scripts/quality_gate.py exhaustive
    python scripts/quality_gate.py strict --dry-run
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]

STANDARD_TARGETS = [
    "tests/test_architecture_constraints.py",
    "tests/test_architecture_guard.py",
    "tests/test_quality_gate.py",
    "tests/test_agent_workflow_docs.py",
    "tests/test_doc_freshness.py",
    "tests/test_event_record_read_policy.py",
    "tests/test_app_service.py",
    "tests/test_events.py::TestEventSemanticContract",
    "tests/test_route_mutation_state_machine.py",
    "tests/test_terrain_mutation_state_machine.py",
    "tests/test_location_rename_state_machine.py",
    "tests/test_route_status_projection.py",
    "tests/test_location_history_projection.py",
    "tests/test_pr_k_architecture_boundaries.py",
    "tests/test_pr_k_event_record_contracts.py",
    "tests/test_pr_k_id_type_smoke.py",
    "tests/test_era_civilization_state_machine.py",
    "tests/test_era_timeline_projection.py",
    "tests/test_pr_k_occupation_state_machine.py",
    "tests/test_pr_k_observation_projections.py",
    "tests/test_pr_k_save_contracts.py",
    "tests/test_war_map_projection.py",
    "tests/test_world_change_report_projection.py",
    "tests/test_world_change_properties.py",
    "tests/test_natural_world_changes.py",
    "tests/test_harness_scenarios.py",
    "tests/test_map_visible_harness.py",
]

PLAYTEST_TARGETS = [
    "tests/test_world_health.py",
    "tests/test_world_health_stats.py",
]

LINT_TARGETS = [
    ".",
]

DEFAULT_EXCLUDES = [
    "node_modules",
    "__pycache__",
    ".claude",
    ".worktrees",
    ".trunk",
]

WORLD_TYPECHECK_EXCLUSIONS: dict[str, str] = {}


@dataclass(frozen=True)
class CommandSpec:
    label: str
    argv: List[str]


def _pytest_command(targets: Sequence[str]) -> CommandSpec:
    return CommandSpec(
        label="pytest",
        argv=[sys.executable, "-m", "pytest", "-q", *targets],
    )


def _playtest_command(targets: Sequence[str] | None = None) -> CommandSpec:
    return CommandSpec(
        label="playtest",
        argv=[sys.executable, "-m", "pytest", "-q", *(targets or PLAYTEST_TARGETS)],
    )


def _flake8_command(targets: Sequence[str]) -> CommandSpec:
    exclude_value = ",".join(DEFAULT_EXCLUDES)
    return CommandSpec(
        label="flake8",
        argv=[
            sys.executable,
            "-m",
            "flake8",
            "--jobs",
            "1",
            "--max-line-length=120",
            f"--exclude={exclude_value}",
            *targets,
        ],
    )


def _complexity_command(targets: Sequence[str]) -> CommandSpec:
    exclude_value = ",".join(DEFAULT_EXCLUDES)
    return CommandSpec(
        label="complexity",
        argv=[
            sys.executable,
            "-m",
            "flake8",
            "--jobs",
            "1",
            "--max-line-length=120",
            "--max-complexity=25",
            f"--exclude={exclude_value}",
            *targets,
        ],
    )


TYPECHECK_TARGETS = [
    "fantasy_simulator/adventure",
    "fantasy_simulator/character.py",
    "fantasy_simulator/character_model",
    "fantasy_simulator/combat_system",
    "fantasy_simulator/content",
    "fantasy_simulator/events",
    "fantasy_simulator/observation",
    "fantasy_simulator/reports",
    "fantasy_simulator/rumor",
    "fantasy_simulator/simulation/event_recorder.py",
    "fantasy_simulator/simulation/queries.py",
    "fantasy_simulator/simulation/query_presenters.py",
    "fantasy_simulator/simulation/timeline_world_changes.py",
    "fantasy_simulator/simulation/world_change_driver.py",
    "fantasy_simulator/terrain",
    "fantasy_simulator/ui/presenters.py",
    "fantasy_simulator/ui/view_models.py",
    "fantasy_simulator/world_actor",
    "fantasy_simulator/world_arc",
    "fantasy_simulator/world_calendar",
    "fantasy_simulator/world_core",
    "fantasy_simulator/world_dynamics",
    "fantasy_simulator/world_event",
    "fantasy_simulator/world_history",
    "fantasy_simulator/world_language",
    "fantasy_simulator/world_location",
    "fantasy_simulator/world_map",
    "fantasy_simulator/world_memory",
    "fantasy_simulator/world_persistence",
    "fantasy_simulator/world_topology",
    "fantasy_simulator/world_state",
    "fantasy_simulator/world_structure",
    "fantasy_simulator/world_change",
    "fantasy_simulator/worldgen",
    "scripts/architecture_guard.py",
    "tools/worldgen_poc",
]


def _mypy_command(targets: Sequence[str]) -> CommandSpec:
    return CommandSpec(
        label="mypy",
        argv=[
            sys.executable,
            "-m",
            "mypy",
            "--follow-imports=silent",
            *targets,
        ],
    )


def build_profile_commands(profile: str, pytest_targets: Sequence[str] | None = None) -> List[CommandSpec]:
    """Return the commands associated with a quality gate profile."""
    targets = list(pytest_targets or [])

    if profile == "minimal":
        if not targets:
            raise ValueError("minimal profile requires at least one --pytest-target")
        return [_pytest_command(targets)]

    commands: List[CommandSpec] = []
    if targets:
        commands.append(_pytest_command(targets))

    if profile == "standard":
        commands.append(_pytest_command(STANDARD_TARGETS))
        return commands

    if profile == "playtest":
        commands.append(_playtest_command())
        return commands

    if profile == "strict":
        commands.append(_pytest_command(STANDARD_TARGETS))
        commands.append(_flake8_command(LINT_TARGETS))
        commands.append(_complexity_command(LINT_TARGETS))
        commands.append(_mypy_command(TYPECHECK_TARGETS))
        commands.append(_playtest_command())
        return commands

    if profile == "exhaustive":
        commands.append(_flake8_command(LINT_TARGETS))
        commands.append(_complexity_command(LINT_TARGETS))
        commands.append(_mypy_command(TYPECHECK_TARGETS))
        commands.append(_pytest_command([]))
        return commands

    raise ValueError(f"Unknown profile: {profile}")


def _format_command(argv: Sequence[str]) -> str:
    return " ".join(argv)


def run_commands(commands: Iterable[CommandSpec], *, dry_run: bool = False) -> int:
    """Execute command specs in order, stopping on first failure."""
    for spec in commands:
        print(f"[quality-gate] {spec.label}: {_format_command(spec.argv)}")
        if dry_run:
            continue
        result = subprocess.run(spec.argv, cwd=REPO_ROOT, check=False)
        if result.returncode != 0:
            return result.returncode
    return 0


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "profile",
        choices=("minimal", "standard", "playtest", "strict", "exhaustive"),
        help="Verification profile to run.",
    )
    parser.add_argument(
        "--pytest-target",
        action="append",
        default=[],
        help="Extra pytest selector(s). Useful for changed-area checks in minimal mode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        commands = build_profile_commands(args.profile, pytest_targets=args.pytest_target)
    except ValueError as exc:
        print(f"[quality-gate] {exc}", file=sys.stderr)
        return 2
    return run_commands(commands, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
