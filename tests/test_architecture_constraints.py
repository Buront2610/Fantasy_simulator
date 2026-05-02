"""Structural guardrails for repo-level architecture and legacy adapters."""

from __future__ import annotations

import ast
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "fantasy_simulator"
REPORTS_MODULE = "fantasy_simulator.reports"
WORLD_DATA_MODULE = "fantasy_simulator.content.world_data"
ADVENTURE_FACADE_MODULE = "fantasy_simulator.adventure"
ADVENTURE_DOMAIN_MODULE = "fantasy_simulator.adventure_domain"
ADVENTURE_EXPORTS_MODULE = "fantasy_simulator.adventure_exports"


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


def _imports_module(path: Path, module_name: str) -> list[str]:
    return [
        target
        for target in _iter_import_targets(path)
        if target == module_name or target.startswith(f"{module_name}.")
    ]


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


def _iter_history_attribute_accesses(path: Path) -> list[tuple[str, int]]:
    """Return (base_name, lineno) for direct `*.history` attribute accesses."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.attr != "history":
            continue
        if isinstance(node.value, ast.Name):
            matches.append((node.value.id, int(getattr(node, "lineno", -1))))
    return matches


def _iter_attribute_accesses(path: Path, attribute_name: str) -> list[tuple[str, int, str]]:
    """Return (base_name, lineno, function_name) for direct attribute reads."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches: list[tuple[str, int, str]] = []

    class AttributeReadVisitor(ast.NodeVisitor):
        def __init__(self) -> None:
            self.function_stack: list[str] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.function_stack.append(node.name)
            self.generic_visit(node)
            self.function_stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.function_stack.append(node.name)
            self.generic_visit(node)
            self.function_stack.pop()

        def visit_Attribute(self, node: ast.Attribute) -> None:
            if (
                node.attr == attribute_name
                and isinstance(node.ctx, ast.Load)
                and isinstance(node.value, ast.Name)
            ):
                function_name = self.function_stack[-1] if self.function_stack else "<module>"
                matches.append((node.value.id, int(getattr(node, "lineno", -1)), function_name))
            self.generic_visit(node)

    AttributeReadVisitor().visit(tree)
    return matches


def _iter_attribute_calls(path: Path, attribute_name: str) -> list[tuple[str, int]]:
    """Return (base_name, lineno) for direct `*.attribute_name(...)` calls."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matches: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != attribute_name:
            continue
        if isinstance(node.func.value, ast.Name):
            matches.append((node.func.value.id, int(getattr(node, "lineno", -1))))
    return matches


def _production_files() -> list[Path]:
    return sorted(path for path in PACKAGE_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def _adventure_helper_files() -> list[Path]:
    allowed_domain_facade = PACKAGE_ROOT / "adventure_domain.py"
    return sorted(
        path
        for path in PACKAGE_ROOT.glob("adventure_*.py")
        if path != allowed_domain_facade
    )


def test_adventure_helper_modules_do_not_import_adventure_facades() -> None:
    forbidden_modules = (ADVENTURE_FACADE_MODULE, ADVENTURE_DOMAIN_MODULE)

    for path in _adventure_helper_files():
        forbidden = [
            target
            for module_name in forbidden_modules
            for target in _imports_module(path, module_name)
        ]
        assert forbidden == [], f"{path} imports adventure facade modules: {forbidden}"


def test_adventure_domain_facade_imports_only_adventure_exports_facade() -> None:
    path = PACKAGE_ROOT / "adventure_domain.py"
    imports = _iter_import_targets(path)
    forbidden = [
        target
        for target in imports
        if target.startswith("fantasy_simulator.adventure")
        and not (target == ADVENTURE_EXPORTS_MODULE or target.startswith(f"{ADVENTURE_EXPORTS_MODULE}."))
    ]

    assert forbidden == [], f"{path} imports adventure modules other than adventure_exports: {forbidden}"
    assert _imports_module(path, ADVENTURE_EXPORTS_MODULE), (
        "adventure_domain.py should re-export adventure_exports"
    )


def test_only_adventure_entrypoint_imports_adventure_domain_facade() -> None:
    allowed = {PACKAGE_ROOT / "adventure.py"}

    for path in _production_files():
        if path in allowed or path.name == "adventure_domain.py":
            continue
        forbidden = _imports_module(path, ADVENTURE_DOMAIN_MODULE)
        assert forbidden == [], f"{path} imports adventure_domain facade: {forbidden}"


def test_adventure_domain_all_matches_adventure_exports_all() -> None:
    from fantasy_simulator import adventure_domain, adventure_exports

    assert adventure_domain.__all__ == adventure_exports.__all__
    for name in adventure_exports.__all__:
        assert getattr(adventure_domain, name) is getattr(adventure_exports, name)


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
        PACKAGE_ROOT / "world_persistence.py",
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
        accesses = [
            (base, lineno)
            for base, lineno in _iter_history_attribute_accesses(path)
            if base in {"self", "sim", "simulator"}
        ]
        if path in allowed:
            continue
        assert accesses == [], (
            f"Simulator.history access escaped legacy adapter files in {path}: {accesses}"
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


def test_world_data_legacy_projection_symbol_imports_are_scoped() -> None:
    projection_names = {"WORLD_LORE", "RACES", "JOBS", "DEFAULT_LOCATIONS"}
    allowed = {
        PACKAGE_ROOT / "terrain.py",
        PACKAGE_ROOT / "persistence" / "migrations.py",
    }

    for path in _production_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module != WORLD_DATA_MODULE:
                continue
            imported = {alias.name for alias in node.names}
            if imported.isdisjoint(projection_names):
                continue
            assert path in allowed, (
                f"Legacy world_data projections imported outside allowed modules in {path}: "
                f"{sorted(imported & projection_names)}"
            )


def test_world_data_imports_stay_in_legacy_compatibility_modules() -> None:
    allowed = {
        PACKAGE_ROOT / "character.py",
        PACKAGE_ROOT / "character_creator.py",
        PACKAGE_ROOT / "events.py",
        PACKAGE_ROOT / "terrain.py",
        PACKAGE_ROOT / "world.py",
        PACKAGE_ROOT / "persistence" / "migrations.py",
    }
    for path in _production_files():
        if path in allowed:
            continue
        forbidden = [
            target
            for target in _iter_import_targets(path)
            if target == WORLD_DATA_MODULE or target.startswith(f"{WORLD_DATA_MODULE}.")
        ]
        assert forbidden == [], f"{path} imports legacy world_data compatibility projections: {forbidden}"


def test_character_max_age_reads_stay_in_lifecycle_compatibility_fallback() -> None:
    allowed = {
        PACKAGE_ROOT / "events_lifecycle.py",
    }

    for path in _production_files():
        accesses = _iter_attribute_accesses(path, "max_age")
        if path in allowed:
            assert [(base, function_name) for base, _, function_name in accesses] == [
                ("char", "character_lifespan_years")
            ], (
                f"Character.max_age compatibility fallback moved in {path}: {accesses}"
            )
            continue
        assert accesses == [], f"Character.max_age read escaped lifecycle compatibility fallback in {path}: {accesses}"


def test_display_event_log_restore_helper_stays_load_only() -> None:
    allowed = {
        PACKAGE_ROOT / "world_persistence.py",
    }

    for path in _production_files():
        calls = _iter_attribute_calls(path, "_restore_display_event_log_for_load")
        if path in allowed:
            assert [base for base, _ in calls] == ["world"], (
                f"event_log load restore helper moved in {path}: {calls}"
            )
            continue
        assert calls == [], f"event_log load restore helper escaped load path in {path}: {calls}"


def test_td3_split_modules_import_event_models_directly_not_events_facade() -> None:
    targets = {
        PACKAGE_ROOT / "world_event_log.py",
        PACKAGE_ROOT / "world_event_state.py",
    }
    for path in targets:
        imports = _iter_import_targets(path)
        assert all(not target.startswith("fantasy_simulator.events") for target in imports), (
            f"{path} should import event models directly, not events facade"
        )
        assert any(target.startswith("fantasy_simulator.event_models") for target in imports), (
            f"{path} must import canonical event model module"
        )


def test_simulation_modules_import_event_models_for_event_contract_types() -> None:
    targets = {
        PACKAGE_ROOT / "simulation" / "engine.py",
        PACKAGE_ROOT / "simulation" / "event_recorder.py",
        PACKAGE_ROOT / "simulation" / "queries.py",
    }
    forbidden_names = {"EventResult", "WorldEventRecord", "generate_record_id"}

    for path in targets:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module_name = ".".join(_resolve_import(_module_name(path), node)[0].split(".")[:-1]) if node.names else ""
            imported_names = {alias.name for alias in node.names}
            if module_name == "fantasy_simulator.events":
                assert forbidden_names.isdisjoint(imported_names), (
                    f"{path} must import event contract types from event_models, not events facade"
                )


def test_world_module_imports_event_models_not_events_facade_for_contract_types() -> None:
    path = PACKAGE_ROOT / "world.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden_names = {"WorldEventRecord", "EventResult", "generate_record_id"}
    saw_event_models_import = False

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module_name = ".".join(_resolve_import(_module_name(path), node)[0].split(".")[:-1]) if node.names else ""
        imported_names = {alias.name for alias in node.names}
        if module_name == "fantasy_simulator.events":
            assert forbidden_names.isdisjoint(imported_names), (
                "world.py must import event contract types from event_models, not events facade"
            )
        if module_name == "fantasy_simulator.event_models" and "WorldEventRecord" in imported_names:
            saw_event_models_import = True

    assert saw_event_models_import, "world.py must import WorldEventRecord from event_models"


def test_reports_module_imports_world_event_record_from_event_models() -> None:
    path = PACKAGE_ROOT / "reports.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported_from_events = False
    imported_from_event_models = False

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module_name = ".".join(_resolve_import(_module_name(path), node)[0].split(".")[:-1]) if node.names else ""
        imported_names = {alias.name for alias in node.names}
        if "WorldEventRecord" not in imported_names:
            continue
        if module_name == "fantasy_simulator.events":
            imported_from_events = True
        if module_name == "fantasy_simulator.event_models":
            imported_from_event_models = True

    assert not imported_from_events, "reports.py should not import WorldEventRecord from events facade"
    assert imported_from_event_models, "reports.py should import WorldEventRecord from event_models"


def test_rumor_module_imports_world_event_record_from_event_models() -> None:
    path = PACKAGE_ROOT / "rumor.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported_from_events = False
    imported_from_event_models = False

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module_name = ".".join(_resolve_import(_module_name(path), node)[0].split(".")[:-1]) if node.names else ""
        imported_names = {alias.name for alias in node.names}
        if "WorldEventRecord" not in imported_names:
            continue
        if module_name == "fantasy_simulator.events":
            imported_from_events = True
        if module_name == "fantasy_simulator.event_models":
            imported_from_event_models = True

    assert not imported_from_events, "rumor.py should not import WorldEventRecord from events facade"
    assert imported_from_event_models, "rumor.py should import WorldEventRecord from event_models"
