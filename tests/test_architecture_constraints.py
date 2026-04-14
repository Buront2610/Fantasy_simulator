"""Structural guardrails for repo-level architecture and legacy adapters."""

from __future__ import annotations

import ast
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "fantasy_simulator"
REPORTS_MODULE = "fantasy_simulator.reports"


def _module_name(path: Path) -> str:
    relative = path.relative_to(PROJECT_ROOT).with_suffix("")
    return ".".join(relative.parts)


def _resolve_import(current_module: str, node: ast.ImportFrom) -> list[str]:
    current_package = current_module.split(".")[:-1]
    if node.level:
        base = current_package[: len(current_package) - (node.level - 1)]
    else:
        base = []
    resolved_base = base + (node.module.split(".") if node.module else [])
    if not node.names:
        return [".".join(resolved_base)] if resolved_base else []

    resolved_targets: list[str] = []
    for alias in node.names:
        if alias.name == "*":
            if resolved_base:
                resolved_targets.append(".".join(resolved_base))
            continue
        parts = resolved_base + alias.name.split(".")
        if parts:
            resolved_targets.append(".".join(parts))
    return resolved_targets


def _iter_import_targets(path: Path) -> list[str]:
    module_name = _module_name(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.extend(_resolve_import(module_name, node))
    return imports


def test_resolve_import_expands_relative_package_aliases() -> None:
    node = ast.parse("from .. import persistence").body[0]

    assert isinstance(node, ast.ImportFrom)
    assert _resolve_import("fantasy_simulator.ui.screens", node) == ["fantasy_simulator.persistence"]


def test_resolve_import_expands_aliases_under_relative_module() -> None:
    node = ast.parse("from ..persistence import save_load").body[0]

    assert isinstance(node, ast.ImportFrom)
    assert _resolve_import("fantasy_simulator.ui.screens", node) == ["fantasy_simulator.persistence.save_load"]


def _iter_attribute_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)]


def _production_files() -> list[Path]:
    return sorted(path for path in PACKAGE_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def test_simulation_layer_does_not_import_ui_or_persistence() -> None:
    for path in sorted((PACKAGE_ROOT / "simulation").glob("*.py")):
        forbidden = [
            target
            for target in _iter_import_targets(path)
            if target.startswith("fantasy_simulator.ui")
            or target.startswith("fantasy_simulator.persistence")
        ]
        assert forbidden == [], f"{path} imports forbidden modules: {forbidden}"


def test_persistence_layer_does_not_import_ui() -> None:
    for path in sorted((PACKAGE_ROOT / "persistence").glob("*.py")):
        forbidden = [
            target
            for target in _iter_import_targets(path)
            if target.startswith("fantasy_simulator.ui")
        ]
        assert forbidden == [], f"{path} imports forbidden modules: {forbidden}"


def test_core_ui_modules_do_not_import_simulation_or_persistence() -> None:
    allowed_composition_file = PACKAGE_ROOT / "ui" / "screens.py"
    for path in sorted((PACKAGE_ROOT / "ui").glob("*.py")):
        if path == allowed_composition_file:
            continue
        forbidden = [
            target
            for target in _iter_import_targets(path)
            if target.startswith("fantasy_simulator.simulation")
            or target.startswith("fantasy_simulator.persistence")
        ]
        assert forbidden == [], f"{path} imports forbidden modules: {forbidden}"


def test_direct_event_log_access_stays_in_compatibility_layers() -> None:
    allowed = {
        PACKAGE_ROOT / "world.py",
        PACKAGE_ROOT / "simulation" / "queries.py",
    }
    for path in _production_files():
        if path in allowed:
            continue
        assert "event_log" not in _iter_attribute_names(path), (
            f"Direct event_log access escaped compatibility layers in {path}"
        )


def test_production_code_does_not_call_legacy_events_by_type() -> None:
    allowed_definition = PACKAGE_ROOT / "simulation" / "queries.py"
    pattern = re.compile(r"\.events_by_type\(")
    for path in _production_files():
        if path == allowed_definition:
            continue
        assert pattern.search(path.read_text(encoding="utf-8")) is None, (
            f"Legacy events_by_type() call found in {path}"
        )


def test_simulation_history_access_stays_in_legacy_adapter_files() -> None:
    allowed = {
        PACKAGE_ROOT / "simulation" / "engine.py",
        PACKAGE_ROOT / "simulation" / "event_recorder.py",
        PACKAGE_ROOT / "simulation" / "queries.py",
    }
    for path in sorted((PACKAGE_ROOT / "simulation").glob("*.py")):
        if path in allowed:
            continue
        assert "self.history" not in path.read_text(encoding="utf-8"), (
            f"Simulator.history access escaped legacy adapter files in {path}"
        )


def test_reports_module_does_not_import_ui_layers() -> None:
    path = PACKAGE_ROOT / "reports.py"
    forbidden = [
        target
        for target in _iter_import_targets(path)
        if target.startswith("fantasy_simulator.ui")
    ]
    assert forbidden == [], f"{path} imports UI modules: {forbidden}"


def test_core_ui_modules_do_not_import_reports_module() -> None:
    allowed_composition_file = PACKAGE_ROOT / "ui" / "screens.py"
    for path in sorted((PACKAGE_ROOT / "ui").glob("*.py")):
        # screens.py is the composition layer that can orchestrate report output.
        if path == allowed_composition_file:
            continue
        forbidden = [
            target
            for target in _iter_import_targets(path)
            if target == REPORTS_MODULE or target.startswith(f"{REPORTS_MODULE}.")
        ]
        assert forbidden == [], f"{path} imports report modules: {forbidden}"
