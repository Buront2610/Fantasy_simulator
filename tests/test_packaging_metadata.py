"""Lightweight checks for packaging metadata and packaging-related ignore rules."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_TEXT = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
GITIGNORE_TEXT = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")


def test_pyproject_includes_setting_bundle_package_data() -> None:
    assert "[tool.setuptools.package-data]" in PYPROJECT_TEXT
    assert '"fantasy_simulator.content" = ["bundles/*.json"]' in PYPROJECT_TEXT


def test_gitignore_covers_packaging_artifacts() -> None:
    assert "*.egg-info/" in GITIGNORE_TEXT
    assert "build/" in GITIGNORE_TEXT
    assert "dist/" in GITIGNORE_TEXT
