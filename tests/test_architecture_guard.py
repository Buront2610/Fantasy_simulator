"""Tests for the static architecture fitness guard."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.architecture_guard import _path_matches, load_config, run_checks, validate_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_architecture_guard_reports_import_and_call_boundary_violations(tmp_path: Path) -> None:
    _write(
        tmp_path / "pkg" / "domain" / "service.py",
        "\n".join(
            [
                "from pkg.ui import screen",
                "",
                "def run():",
                "    print(screen)",
            ]
        ),
    )
    _write(tmp_path / "pkg" / "ui" / "screen.py", "TITLE = 'demo'\n")

    config = {
        "source_roots": ["pkg"],
        "import_boundary_rules": [
            {
                "name": "domain_is_ui_free",
                "include": ["pkg/domain/*.py"],
                "forbid": ["pkg.ui"],
            }
        ],
        "call_boundary_rules": [
            {
                "name": "domain_has_no_direct_io",
                "include": ["pkg/domain/*.py"],
                "forbid_calls": ["print"],
            }
        ],
    }

    violations = run_checks(tmp_path, config)

    assert [violation.rule for violation in violations] == [
        "domain_is_ui_free",
        "domain_has_no_direct_io",
    ]
    assert "forbidden import 'pkg.ui.screen'" in violations[0].message
    assert "forbidden call 'print'" in violations[1].message


def test_architecture_guard_reports_cognitive_complexity_budget(tmp_path: Path) -> None:
    _write(
        tmp_path / "pkg" / "domain" / "branching.py",
        "\n".join(
            [
                "def tangled(items):",
                "    total = 0",
                "    for item in items:",
                "        if item:",
                "            if item > 10 and item < 20:",
                "                total += item",
                "            else:",
                "                continue",
                "    return total",
            ]
        ),
    )

    config = {
        "source_roots": ["pkg"],
        "complexity": {
            "include": ["pkg/**/*.py"],
            "max_cognitive_complexity": 3,
        },
    }

    violations = run_checks(tmp_path, config)

    assert len(violations) == 1
    assert violations[0].rule == "complexity_budget"
    assert "cognitive complexity" in violations[0].message
    assert "pkg/domain/branching.py::tangled" in violations[0].message


def test_path_globs_are_depth_aware() -> None:
    assert _path_matches("fantasy_simulator/world.py", ["fantasy_simulator/*.py"])
    assert not _path_matches("fantasy_simulator/world_change/foo.py", ["fantasy_simulator/*.py"])
    assert _path_matches("fantasy_simulator/world_change/foo.py", ["fantasy_simulator/**/*.py"])


def test_complexity_overrides_require_reason() -> None:
    config = {
        "source_roots": ["pkg"],
        "complexity": {
            "overrides": [
                {
                    "target": "pkg/domain/service.py::run",
                    "max_cognitive_complexity": 99,
                }
            ]
        },
    }

    try:
        validate_config(config)
    except TypeError as exc:
        assert "requires a non-empty reason" in str(exc)
    else:
        raise AssertionError("Expected budget overrides without a reason to fail")


def test_complexity_overrides_require_debt_ledger_metadata() -> None:
    base_override = {
        "target": "pkg/domain/service.py::run",
        "reason": "Formerly complex branch preserved as an example.",
        "max_cognitive_complexity": 99,
    }

    for missing_key, message in (
        ("owner", "requires a non-empty owner"),
        ("removal_condition", "requires a non-empty removal_condition"),
    ):
        override = {
            **base_override,
            "owner": "architecture-maintainers",
            "removal_condition": "Remove when the function fits the default complexity budget.",
        }
        override.pop(missing_key)
        config = {
            "source_roots": ["pkg"],
            "complexity": {
                "overrides": [override],
            },
        }

        try:
            validate_config(config)
        except TypeError as exc:
            assert message in str(exc)
        else:
            raise AssertionError(f"Expected overrides without {missing_key} to fail")


def test_complexity_budgets_reject_bool_values() -> None:
    for complexity in (
        {"max_function_lines": True},
        {
            "overrides": [
                {
                    "target": "pkg/domain/service.py::Service",
                    "reason": "Example override.",
                    "owner": "architecture-maintainers",
                    "removal_condition": "Remove when the class fits the default budget.",
                    "max_class_lines": True,
                }
            ]
        },
    ):
        try:
            validate_config({"source_roots": ["pkg"], "complexity": complexity})
        except TypeError as exc:
            assert "Expected an integer or null" in str(exc)
        else:
            raise AssertionError("Expected bool complexity budget to fail")


def test_relaxed_complexity_overrides_fail_when_no_longer_needed(tmp_path: Path) -> None:
    _write(
        tmp_path / "pkg" / "domain" / "simple.py",
        "\n".join(
            [
                "def run():",
                "    return 1",
            ]
        ),
    )

    config = {
        "source_roots": ["pkg"],
        "complexity": {
            "include": ["pkg/**/*.py"],
            "max_cognitive_complexity": 5,
            "overrides": [
                {
                    "target": "pkg/domain/simple.py::run",
                    "reason": "Formerly complex branch preserved as an example.",
                    "owner": "architecture-maintainers",
                    "removal_condition": "Remove when the function fits the default complexity budget.",
                    "max_cognitive_complexity": 99,
                }
            ],
        },
    }

    violations = run_checks(tmp_path, config)

    assert len(violations) == 1
    assert violations[0].rule == "stale_complexity_override"
    assert "remove relaxed override 99" in violations[0].message


def test_missing_complexity_override_targets_fail(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "domain" / "simple.py", "def run():\n    return 1\n")

    config = {
        "source_roots": ["pkg"],
        "complexity": {
            "include": ["pkg/**/*.py"],
            "max_cognitive_complexity": 5,
            "overrides": [
                {
                    "target": "pkg/domain/simple.py::rn",
                    "reason": "Typo should not be silently ignored.",
                    "owner": "architecture-maintainers",
                    "removal_condition": "Remove when the target name points at an observed metric.",
                    "max_cognitive_complexity": 99,
                }
            ],
        },
    }

    violations = run_checks(tmp_path, config)

    assert len(violations) == 1
    assert violations[0].rule == "unused_complexity_override"
    assert "pkg/domain/simple.py::rn" in violations[0].message


def test_architecture_guard_reports_package_import_cycles(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "domain" / "alpha.py", "from pkg.domain import beta\n")
    _write(tmp_path / "pkg" / "domain" / "beta.py", "from pkg.domain import alpha\n")

    config = {
        "source_roots": ["pkg"],
        "acyclic_package_rules": [
            {
                "name": "domain_is_acyclic",
                "include": ["pkg/domain/*.py"],
            }
        ],
    }

    violations = run_checks(tmp_path, config)

    assert len(violations) == 1
    assert violations[0].rule == "domain_is_acyclic"
    assert "import cycle detected" in violations[0].message
    assert "pkg.domain.alpha" in violations[0].message
    assert "pkg.domain.beta" in violations[0].message


def test_architecture_guard_reports_legacy_mutation_helper_calls(tmp_path: Path) -> None:
    _write(
        tmp_path / "pkg" / "feature.py",
        "\n".join(
            [
                "def run(world):",
                "    world.rename_location('loc_a', 'New Name')",
            ]
        ),
    )

    config = {
        "source_roots": ["pkg"],
        "call_boundary_rules": [
            {
                "name": "production_uses_canonical_api",
                "include": ["pkg/*.py"],
                "forbid_calls": ["rename_location"],
            }
        ],
    }

    violations = run_checks(tmp_path, config)

    assert len(violations) == 1
    assert violations[0].rule == "production_uses_canonical_api"
    assert "forbidden call 'world.rename_location'" in violations[0].message


def test_repository_architecture_guard_config_is_valid_json() -> None:
    config_path = PROJECT_ROOT / "architecture_guard.json"

    json.loads(config_path.read_text(encoding="utf-8"))


def test_repository_default_complexity_budgets_stay_tight() -> None:
    config = load_config(PROJECT_ROOT / "architecture_guard.json")
    complexity = config["complexity"]

    assert complexity["max_cyclomatic_complexity"] <= 20
    assert complexity["max_cognitive_complexity"] <= 25
    assert complexity["max_function_lines"] <= 80
    assert complexity["max_public_methods"] <= 12
    assert complexity["max_class_lines"] <= 220
    assert complexity["max_first_party_imports"] <= 12


def test_repository_architecture_guard_passes() -> None:
    violations = run_checks(PROJECT_ROOT, load_config(PROJECT_ROOT / "architecture_guard.json"))

    assert violations == []
