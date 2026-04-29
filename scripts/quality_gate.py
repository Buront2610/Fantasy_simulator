"""Profile-based verification runner for local agent workflows.

Usage examples
--------------
    python scripts/quality_gate.py minimal --pytest-target tests/test_character_creator.py
    python scripts/quality_gate.py standard
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
    "tests/test_quality_gate.py",
    "tests/test_agent_workflow_docs.py",
    "tests/test_doc_freshness.py",
    "tests/test_event_record_read_policy.py",
    "tests/test_harness_scenarios.py",
    "tests/test_map_visible_harness.py",
]

LINT_TARGETS = [
    ".",
]

DEFAULT_EXCLUDES = [
    "node_modules",
    "__pycache__",
    ".claude",
    ".worktrees",
]

WORLD_TYPECHECK_EXCLUSIONS = {
    "fantasy_simulator/world_calendar.py": "generic calendar-change protocol still needs attribute-bound tightening",
    "fantasy_simulator/world_event_log.py": "read-only list compatibility adapter needs list-subclass override cleanup",
    "fantasy_simulator/world_load_normalizer.py": "legacy load normalization accepts nullable location references",
    "fantasy_simulator/world_route_graph.py": (
        "observable list compatibility adapter needs list-subclass override cleanup"
    ),
    "fantasy_simulator/world_topology_state.py": "topology payload validators still accept broad legacy dictionaries",
}


@dataclass(frozen=True)
class CommandSpec:
    label: str
    argv: List[str]


def _pytest_command(targets: Sequence[str]) -> CommandSpec:
    return CommandSpec(
        label="pytest",
        argv=[sys.executable, "-m", "pytest", "-q", *targets],
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
    "fantasy_simulator/adventure.py",
    "fantasy_simulator/adventure_domain.py",
    "fantasy_simulator/character.py",
    "fantasy_simulator/character_domain.py",
    "fantasy_simulator/event_models.py",
    "fantasy_simulator/location_observation.py",
    "fantasy_simulator/ui/presenters.py",
    "fantasy_simulator/ui/view_models.py",
    "fantasy_simulator/world_actor_api.py",
    "fantasy_simulator/world_actor_index.py",
    "fantasy_simulator/world_bundle_transition.py",
    "fantasy_simulator/world_calendar_api.py",
    "fantasy_simulator/world_calendar_facade.py",
    "fantasy_simulator/world_dynamic_changes.py",
    "fantasy_simulator/world_event_api.py",
    "fantasy_simulator/world_event_history.py",
    "fantasy_simulator/world_event_index.py",
    "fantasy_simulator/world_event_log_api.py",
    "fantasy_simulator/world_event_log_facade.py",
    "fantasy_simulator/world_event_queries.py",
    "fantasy_simulator/world_event_state.py",
    "fantasy_simulator/world_language_api.py",
    "fantasy_simulator/world_language_facade.py",
    "fantasy_simulator/world_language.py",
    "fantasy_simulator/world_location_references.py",
    "fantasy_simulator/world_location_state.py",
    "fantasy_simulator/world_location_structure.py",
    "fantasy_simulator/world_memory_api.py",
    "fantasy_simulator/world_memory.py",
    "fantasy_simulator/world_persistence.py",
    "fantasy_simulator/world_records.py",
    "fantasy_simulator/world_reference_repair.py",
    "fantasy_simulator/world_state_propagation.py",
    "fantasy_simulator/world_state_runtime.py",
    "fantasy_simulator/world_structure_api.py",
    "fantasy_simulator/world_topology_api.py",
    "fantasy_simulator/world_topology_queries.py",
    "fantasy_simulator/world_topology_runtime.py",
    "fantasy_simulator/world_topology.py",
    "fantasy_simulator/worldgen",
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

    if profile == "strict":
        commands.append(_pytest_command(STANDARD_TARGETS))
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
        choices=("minimal", "standard", "strict"),
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
