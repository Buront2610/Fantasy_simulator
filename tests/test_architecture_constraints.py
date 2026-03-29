"""Structural guardrails for repo-level architecture and legacy adapters."""

from __future__ import annotations

import ast
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "fantasy_simulator"


def _module_name(path: Path) -> str:
    relative = path.relative_to(PROJECT_ROOT).with_suffix("")
    return ".".join(relative.parts)


def _resolve_import(current_module: str, node: ast.ImportFrom) -> str:
    current_package = current_module.split(".")[:-1]
    if node.level:
        base = current_package[: len(current_package) - (node.level - 1)]
    else:
        base = []
    if node.module:
        return ".".join(base + node.module.split("."))
    return ".".join(base)


def _iter_import_targets(path: Path) -> list[str]:
    module_name = _module_name(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(_resolve_import(module_name, node))
    return imports


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
