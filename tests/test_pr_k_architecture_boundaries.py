"""PR-K architecture fitness checks for future world-change packages."""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "fantasy_simulator"

HEADLESS_BOUNDARY_FORBIDDEN_PREFIXES = (
    "fantasy_simulator.adventure",
    "fantasy_simulator.character",
    "fantasy_simulator.events",
    "fantasy_simulator.reports",
    "fantasy_simulator.simulation",
    "fantasy_simulator.terrain",
    "fantasy_simulator.ui",
    "fantasy_simulator.world",
    "fantasy_simulator.persistence",
    "fantasy_simulator.event_rendering",
    "fantasy_simulator.world_persistence",
    "rich",
    "textual",
)

HEADLESS_BOUNDARY_FORBIDDEN_SIBLING_PREFIXES = (
    "fantasy_simulator.terrain_",
)


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


def _iter_optional_package_files(package_name: str) -> list[Path]:
    package_dir = PACKAGE_ROOT / package_name
    if not package_dir.exists():
        return []
    return sorted(path for path in package_dir.rglob("*.py") if "__pycache__" not in path.parts)


def _has_forbidden_prefix(target: str, forbidden_prefixes: tuple[str, ...]) -> bool:
    return any(target == prefix or target.startswith(f"{prefix}.") for prefix in forbidden_prefixes)


def _has_forbidden_sibling_prefix(target: str, forbidden_sibling_prefixes: tuple[str, ...]) -> bool:
    return any(target.startswith(prefix) for prefix in forbidden_sibling_prefixes)


def _is_forbidden_import_target(
    target: str,
    forbidden_prefixes: tuple[str, ...],
    forbidden_sibling_prefixes: tuple[str, ...],
) -> bool:
    return _has_forbidden_prefix(target, forbidden_prefixes) or _has_forbidden_sibling_prefix(
        target,
        forbidden_sibling_prefixes,
    )


def _forbidden_imports(
    path: Path,
    forbidden_prefixes: tuple[str, ...],
    forbidden_sibling_prefixes: tuple[str, ...] = (),
) -> list[str]:
    return [
        target
        for target in _iter_import_targets(path)
        if _is_forbidden_import_target(target, forbidden_prefixes, forbidden_sibling_prefixes)
    ]


def test_headless_boundary_matcher_catches_narrow_adapter_edges() -> None:
    forbidden_targets = [
        "fantasy_simulator.terrain",
        "fantasy_simulator.terrain.RouteEdge",
        "fantasy_simulator.terrain_generation",
        "fantasy_simulator.terrain_route_generation.RouteBuilder",
        "fantasy_simulator.ui.map_renderer",
        "fantasy_simulator.persistence.save_load",
        "fantasy_simulator.event_rendering",
        "fantasy_simulator.world_persistence",
        "rich.console",
        "textual.app",
    ]
    allowed_targets = [
        "fantasy_simulator.terrainology",
        "fantasy_simulator.event_models",
        "fantasy_simulator.world_change.commands",
        "fantasy_simulator.observation.route_status_projection",
    ]

    for target in forbidden_targets:
        assert _is_forbidden_import_target(
            target,
            HEADLESS_BOUNDARY_FORBIDDEN_PREFIXES,
            HEADLESS_BOUNDARY_FORBIDDEN_SIBLING_PREFIXES,
        )

    for target in allowed_targets:
        assert not _is_forbidden_import_target(
            target,
            HEADLESS_BOUNDARY_FORBIDDEN_PREFIXES,
            HEADLESS_BOUNDARY_FORBIDDEN_SIBLING_PREFIXES,
        )


def test_future_world_change_package_stays_headless_and_storage_agnostic() -> None:
    for path in _iter_optional_package_files("world_change"):
        forbidden = _forbidden_imports(
            path,
            HEADLESS_BOUNDARY_FORBIDDEN_PREFIXES,
            HEADLESS_BOUNDARY_FORBIDDEN_SIBLING_PREFIXES,
        )
        assert forbidden == [], f"{path} imports forbidden adapter modules: {forbidden}"


def test_future_observation_package_does_not_import_renderers_or_io_adapters() -> None:
    for path in _iter_optional_package_files("observation"):
        forbidden = _forbidden_imports(
            path,
            HEADLESS_BOUNDARY_FORBIDDEN_PREFIXES,
            HEADLESS_BOUNDARY_FORBIDDEN_SIBLING_PREFIXES,
        )
        assert forbidden == [], f"{path} imports forbidden renderer/adapter modules: {forbidden}"
