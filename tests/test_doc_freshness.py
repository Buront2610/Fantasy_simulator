"""Lightweight documentation freshness checks for repo-local source-of-truth docs."""

from __future__ import annotations

import re
from pathlib import Path

from fantasy_simulator.persistence.migrations import CURRENT_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]
README_TEXT = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
PLAN_TEXT = (PROJECT_ROOT / "docs" / "implementation_plan.md").read_text(encoding="utf-8")
ARCHITECTURE_TEXT = (PROJECT_ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
UI_PLAN_TEXT = (PROJECT_ROOT / "docs" / "ui_renovation_plan.md").read_text(encoding="utf-8")


def test_readme_schema_version_matches_current_migration_version() -> None:
    match = re.search(r"`schema_version = (\d+)`", README_TEXT)
    assert match is not None, "README must document the current schema_version"
    assert int(match.group(1)) == CURRENT_VERSION


def test_readme_points_to_implementation_plan_for_roadmap() -> None:
    assert "docs/implementation_plan.md" in README_TEXT
    assert "source of truth" in PLAN_TEXT


def test_readme_and_plan_agree_on_next_step() -> None:
    assert "technical-debt backlog" in README_TEXT
    assert "TD-1〜TD-4" in PLAN_TEXT
    assert "PR-J / PR-K" in README_TEXT


def test_ui_plan_does_not_conflict_with_implementation_plan_next_step() -> None:
    assert "TD-1〜TD-4" in PLAN_TEXT
    assert "TD-1〜TD-4" in UI_PLAN_TEXT
    assert "PR-I は完了" in UI_PLAN_TEXT


def test_architecture_doc_records_canonical_event_store_rules() -> None:
    assert "World.event_records" in ARCHITECTURE_TEXT
    assert "events_by_type()" in ARCHITECTURE_TEXT
    assert "compatibility display buffer" in ARCHITECTURE_TEXT
    assert "Sunset Conditions" in ARCHITECTURE_TEXT
    assert "World.get_compatibility_event_log()" in ARCHITECTURE_TEXT
