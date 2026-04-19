"""Workflow checks for dependency-install source-of-truth alignment."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_TEXT = (PROJECT_ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf-8")


def test_ci_installs_dev_dependencies_from_pyproject() -> None:
    assert 'python -m pip install -e ".[dev]"' in WORKFLOW_TEXT
    assert "pip install pytest flake8" not in WORKFLOW_TEXT


def test_ci_has_optional_ui_contract_job() -> None:
    assert "ui-contract:" in WORKFLOW_TEXT
    assert 'python -m pip install -e ".[dev,ui]"' in WORKFLOW_TEXT
    assert "tests/test_input_backend.py tests/test_render_backend.py -v" in WORKFLOW_TEXT
