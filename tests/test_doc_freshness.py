"""Lightweight documentation freshness checks for repo-local source-of-truth docs."""

from __future__ import annotations

import re
from pathlib import Path

from fantasy_simulator.persistence.migrations import CURRENT_VERSION
from scripts.quality_gate import DEFAULT_EXCLUDES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
README_TEXT = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
AGENTS_TEXT = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
CLAUDE_TEXT = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
CLAUDE_VALIDATE_TEXT = (PROJECT_ROOT / ".claude" / "commands" / "validate.md").read_text(encoding="utf-8")
PYPROJECT_TEXT = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
REQUIREMENTS_DEV_TEXT = (PROJECT_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
PLAN_TEXT = (PROJECT_ROOT / "docs" / "implementation_plan.md").read_text(encoding="utf-8")
ARCHITECTURE_TEXT = (PROJECT_ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
NEXT_VERSION_TEXT = (PROJECT_ROOT / "docs" / "next_version_plan.md").read_text(encoding="utf-8")
UI_PLAN_TEXT = (PROJECT_ROOT / "docs" / "ui_renovation_plan.md").read_text(encoding="utf-8")
TD_STATUS_TEXT = (PROJECT_ROOT / "docs" / "td_backlog_status.md").read_text(encoding="utf-8")
SERIALIZATION_CONTRACT_TEXT = (PROJECT_ROOT / "docs" / "serialization_contract.md").read_text(encoding="utf-8")
RISK_REGISTER_TEXT = (PROJECT_ROOT / "docs" / "risk_register.md").read_text(encoding="utf-8")
LANGUAGE_ENGINE_TEXT = (PROJECT_ROOT / "docs" / "language_engine.md").read_text(encoding="utf-8")


def test_readme_schema_version_matches_current_migration_version() -> None:
    match = re.search(r"`schema_version = (\d+)`", README_TEXT)
    assert match is not None, "README must document the current schema_version"
    assert int(match.group(1)) == CURRENT_VERSION


def test_agent_doc_schema_version_matches_current_migration_version() -> None:
    assert f"現行 schema v{CURRENT_VERSION}" in AGENTS_TEXT
    assert f"現行 v{CURRENT_VERSION}" in CLAUDE_TEXT


def test_next_version_doc_mentions_current_schema_version() -> None:
    assert f"schema v{CURRENT_VERSION} migration" in NEXT_VERSION_TEXT


def test_dependency_metadata_source_of_truth_is_pyproject() -> None:
    assert "[project]" in PYPROJECT_TEXT
    assert "[project.optional-dependencies]" in PYPROJECT_TEXT
    assert 'requires-python = ">=3.10"' in PYPROJECT_TEXT
    assert "pyproject.toml" in README_TEXT
    assert "pyproject.toml" in ARCHITECTURE_TEXT


def test_requirements_dev_is_only_a_pyproject_compatibility_shim() -> None:
    assert REQUIREMENTS_DEV_TEXT.strip() == "-e .[dev]"


def test_pyproject_declares_dev_and_ui_dependency_groups() -> None:
    assert '"pytest>=7.0"' in PYPROJECT_TEXT
    assert '"hypothesis>=6.0"' in PYPROJECT_TEXT
    assert '"flake8>=7.0"' in PYPROJECT_TEXT
    assert '"rich"' in PYPROJECT_TEXT
    assert '"prompt_toolkit"' in PYPROJECT_TEXT
    assert "uv sync --extra dev" in README_TEXT
    assert 'python -m pip install -e ".[dev]"' in README_TEXT


def test_readme_points_to_implementation_plan_for_roadmap() -> None:
    assert "docs/implementation_plan.md" in README_TEXT
    assert "source of truth" in PLAN_TEXT


def test_readme_and_plan_agree_on_next_step() -> None:
    assert "technical-debt backlog as closed" in README_TEXT
    assert "TD-1〜TD-4 の負債解消は完了済み" in PLAN_TEXT
    assert "次に着手すべき実装は **TD-1〜TD-4 の負債解消**" not in PLAN_TEXT
    assert "PR-J's first formal `SettingBundle` authoring pass is complete" in README_TEXT
    assert "次に着手すべき実装は **PR-K: 動的世界変化**" in PLAN_TEXT
    assert "PR-J: 世界観設定整理と初期 Setting Bundle 構築 ← **次はここ**" not in PLAN_TEXT


def test_ui_plan_does_not_conflict_with_implementation_plan_next_step() -> None:
    assert "~~PR-J: 世界観設定整理と初期 Setting Bundle 構築~~ ✅" in PLAN_TEXT
    assert "PR-K: 動的世界変化（war / renaming / terrain mutation / era shift / civilization drift） ← **次はここ**" in PLAN_TEXT
    assert "次段は PR-K で動的世界変化へ入る" in UI_PLAN_TEXT
    assert "次段は TD-1〜TD-4" not in UI_PLAN_TEXT
    assert "PR-H2、PR-I、TD-1〜TD-4 の負債解消、PR-J の世界観 authoring は完了" in UI_PLAN_TEXT


def test_agent_validation_commands_exclude_local_worktrees() -> None:
    expected_exclude = f"--exclude={','.join(DEFAULT_EXCLUDES)}"
    for doc_text in (AGENTS_TEXT, CLAUDE_TEXT, CLAUDE_VALIDATE_TEXT):
        assert expected_exclude in doc_text
        assert "--exclude=node_modules,__pycache__ ." not in doc_text


def test_claude_doc_mentions_focused_mypy_in_ci() -> None:
    assert "focused mypy" in CLAUDE_TEXT


def test_implementation_plan_reflects_bundle_migration_status_for_world_lore_screen() -> None:
    assert "screen_world_lore() は依然として `WORLD_LORE` 定数を直接読む" not in PLAN_TEXT
    assert "screen_world_lore()" in PLAN_TEXT
    assert "bundle source" in PLAN_TEXT


def test_architecture_doc_records_canonical_event_store_rules() -> None:
    assert "World.event_records" in ARCHITECTURE_TEXT
    assert "events_by_type()" in ARCHITECTURE_TEXT
    assert "compatibility display buffer" in ARCHITECTURE_TEXT
    assert "Compatibility Adapter Inventory" in ARCHITECTURE_TEXT
    assert "Simulator.history" in ARCHITECTURE_TEXT
    assert "Sunset Conditions" in ARCHITECTURE_TEXT
    assert "World.get_compatibility_event_log()" in ARCHITECTURE_TEXT
    assert "runtime compatibility projection" in ARCHITECTURE_TEXT
    assert "backward-load compatibility" in ARCHITECTURE_TEXT
    assert "persisted compatibility projection" not in ARCHITECTURE_TEXT
    assert "persisted save snapshots" not in ARCHITECTURE_TEXT


def test_architecture_doc_rejects_legacy_persistence_wording_for_adapters() -> None:
    forbidden = (
        "history persistence may be removed",
        "event_log persistence may be removed",
        "persisted compatibility projection",
    )
    for phrase in forbidden:
        assert phrase not in ARCHITECTURE_TEXT, f"Remove stale architecture wording: {phrase}"


def test_td_backlog_status_tracks_invariants_and_closed_major_split() -> None:
    assert "新機能追加なし" in TD_STATUS_TEXT
    assert "挙動維持" in TD_STATUS_TEXT
    assert "save/load 互換維持" in TD_STATUS_TEXT
    assert "World.event_records" in TD_STATUS_TEXT
    assert "TD-3 Responsibility Split" in TD_STATUS_TEXT
    assert "Current debt status" in TD_STATUS_TEXT
    assert "PR-K の動的世界変化機能" in TD_STATUS_TEXT
    assert "world_key == \"aethoria\"" in TD_STATUS_TEXT
    assert "docs/serialization_contract.md" in TD_STATUS_TEXT
    assert "docs/risk_register.md" in TD_STATUS_TEXT


def test_serialization_contract_documents_conflict_precedence() -> None:
    assert "world.event_records" in SERIALIZATION_CONTRACT_TEXT
    assert "world.event_log" in SERIALIZATION_CONTRACT_TEXT
    assert "language_evolution_history" in SERIALIZATION_CONTRACT_TEXT
    assert "language_runtime_states" in SERIALIZATION_CONTRACT_TEXT
    assert "history wins" in SERIALIZATION_CONTRACT_TEXT
    assert "language_engine.md" in SERIALIZATION_CONTRACT_TEXT
    assert "serialization_contract.md" in LANGUAGE_ENGINE_TEXT


def test_risk_register_tracks_serialization_conflict_risks() -> None:
    assert "Canonical event records" in RISK_REGISTER_TEXT
    assert "Language runtime cache" in RISK_REGISTER_TEXT
    assert "world.event_records" in RISK_REGISTER_TEXT
    assert "language_evolution_history" in RISK_REGISTER_TEXT
    assert "Core serialization logic was not changed" in RISK_REGISTER_TEXT


def test_implementation_plan_mentions_current_observation_and_type_gate_debt_payoff() -> None:
    assert "inspectable" in PLAN_TEXT
    assert "bundle authoring / swap review" in PLAN_TEXT
    assert "type-gate scaffolding" in PLAN_TEXT


def test_architecture_doc_tracks_strict_quality_gate_scope() -> None:
    assert "focused mypy targets" in ARCHITECTURE_TEXT
    assert "newly split `world_*` API/facade/helper modules" in ARCHITECTURE_TEXT


def test_user_docs_mention_strict_quality_gate() -> None:
    for doc_text in (README_TEXT, AGENTS_TEXT, CLAUDE_TEXT):
        assert "python scripts/quality_gate.py strict" in doc_text
        assert "focused mypy" in doc_text
        assert "full pytest" in doc_text


def test_readme_keeps_ci_type_target_wording_non_prescriptive() -> None:
    assert "workflow\ncoverage should be reviewed against the same list" in README_TEXT
    assert "CI should\nkeep the same focused target coverage" not in README_TEXT
