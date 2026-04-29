"""Tests for the profile-based quality gate runner."""

from pathlib import Path

from scripts.quality_gate import TYPECHECK_TARGETS, WORLD_TYPECHECK_EXCLUSIONS, build_profile_commands


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_TEXT = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")


def _pyproject_mypy_files() -> list[str]:
    files: list[str] = []
    in_mypy_files = False
    for line in PYPROJECT_TEXT.splitlines():
        stripped = line.strip()
        if stripped == "files = [":
            in_mypy_files = True
            continue
        if in_mypy_files and stripped == "]":
            return files
        if in_mypy_files:
            files.append(stripped.rstrip(",").strip('"'))
    raise AssertionError("tool.mypy files list not found")


def test_minimal_profile_defaults_to_smoke_target():
    try:
        build_profile_commands("minimal")
    except ValueError as exc:
        assert "requires at least one --pytest-target" in str(exc)
    else:
        raise AssertionError("minimal profile should require explicit pytest targets")


def test_minimal_profile_accepts_explicit_pytest_targets():
    commands = build_profile_commands(
        "minimal",
        pytest_targets=["tests/test_character_creator.py", "tests/test_world.py"],
    )
    assert commands[0].argv[-2:] == [
        "tests/test_character_creator.py",
        "tests/test_world.py",
    ]


def test_standard_profile_runs_targeted_harness_suite():
    commands = build_profile_commands("standard")
    assert len(commands) == 1
    assert commands[0].argv[-7:] == [
        "tests/test_architecture_constraints.py",
        "tests/test_quality_gate.py",
        "tests/test_agent_workflow_docs.py",
        "tests/test_doc_freshness.py",
        "tests/test_event_record_read_policy.py",
        "tests/test_harness_scenarios.py",
        "tests/test_map_visible_harness.py",
    ]


def test_standard_profile_can_prepend_changed_area_pytest():
    commands = build_profile_commands("standard", pytest_targets=["tests/test_character_creator.py"])
    assert len(commands) == 2
    assert commands[0].argv[-1] == "tests/test_character_creator.py"
    assert commands[1].argv[-7:] == [
        "tests/test_architecture_constraints.py",
        "tests/test_quality_gate.py",
        "tests/test_agent_workflow_docs.py",
        "tests/test_doc_freshness.py",
        "tests/test_event_record_read_policy.py",
        "tests/test_harness_scenarios.py",
        "tests/test_map_visible_harness.py",
    ]


def test_strict_profile_includes_targeted_lint_and_full_pytest():
    commands = build_profile_commands("strict")
    assert [command.label for command in commands] == ["pytest", "flake8", "complexity", "mypy", "pytest"]
    assert "." in commands[1].argv
    assert "--max-complexity=25" in commands[2].argv
    assert "." in commands[2].argv
    assert commands[3].argv[-len(TYPECHECK_TARGETS):] == TYPECHECK_TARGETS
    assert len(commands[4].argv) == 4


def test_pyproject_includes_type_gate_scaffolding():
    assert "[tool.mypy]" in PYPROJECT_TEXT
    assert 'follow_imports = "silent"' in PYPROJECT_TEXT
    assert '"fantasy_simulator/world_actor_api.py"' in PYPROJECT_TEXT
    assert '"fantasy_simulator/world_topology_queries.py"' in PYPROJECT_TEXT
    assert '"fantasy_simulator/worldgen"' in PYPROJECT_TEXT
    assert '"tools/worldgen_poc"' in PYPROJECT_TEXT
    assert "check_untyped_defs = true" in PYPROJECT_TEXT


def test_quality_gate_typecheck_targets_match_pyproject_mypy_files():
    assert _pyproject_mypy_files() == TYPECHECK_TARGETS


def test_world_typecheck_targets_are_complete_or_explicitly_excluded():
    world_modules = {
        path.as_posix().removeprefix(PROJECT_ROOT.as_posix() + "/")
        for path in (PROJECT_ROOT / "fantasy_simulator").glob("world_*.py")
    }
    covered = {target for target in TYPECHECK_TARGETS if target.startswith("fantasy_simulator/world_")}
    excluded = set(WORLD_TYPECHECK_EXCLUSIONS)

    assert covered | excluded == world_modules
    assert not covered & excluded
    assert all(reason.strip() for reason in WORLD_TYPECHECK_EXCLUSIONS.values())
