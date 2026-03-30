"""Tests for the profile-based quality gate runner."""

from scripts.quality_gate import build_profile_commands


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
    assert commands[0].argv[-5:] == [
        "tests/test_architecture_constraints.py",
        "tests/test_quality_gate.py",
        "tests/test_agent_workflow_docs.py",
        "tests/test_doc_freshness.py",
        "tests/test_harness_scenarios.py",
    ]


def test_standard_profile_can_prepend_changed_area_pytest():
    commands = build_profile_commands("standard", pytest_targets=["tests/test_character_creator.py"])
    assert len(commands) == 2
    assert commands[0].argv[-1] == "tests/test_character_creator.py"
    assert commands[1].argv[-5:] == [
        "tests/test_architecture_constraints.py",
        "tests/test_quality_gate.py",
        "tests/test_agent_workflow_docs.py",
        "tests/test_doc_freshness.py",
        "tests/test_harness_scenarios.py",
    ]


def test_strict_profile_includes_targeted_lint_and_full_pytest():
    commands = build_profile_commands("strict")
    assert [command.label for command in commands] == ["pytest", "flake8", "pytest"]
    assert "fantasy_simulator" in commands[1].argv
    assert len(commands[2].argv) == 4
