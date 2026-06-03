"""Static architecture fitness checks for CI and local quality gates.

The guard intentionally uses only the standard library so it can run anywhere
the project test suite runs. Rules live in ``architecture_guard.json`` and are
designed as architecture fitness functions: import boundaries, direct I/O
boundaries, and maintainability budgets for complexity and size.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "architecture_guard.json"
BUDGET_OVERRIDE_KEYS = {
    "max_cyclomatic_complexity",
    "max_cognitive_complexity",
    "max_function_lines",
    "max_public_methods",
    "max_class_lines",
    "max_first_party_imports",
}


@dataclass(frozen=True)
class SourceFile:
    path: Path
    relative_path: str
    module_name: str
    tree: ast.AST


@dataclass(frozen=True)
class ImportRef:
    target: str
    line: int


@dataclass(frozen=True)
class CallRef:
    name: str
    line: int


@dataclass(frozen=True)
class FunctionMetric:
    target: str
    path: Path
    line: int
    cyclomatic_complexity: int
    cognitive_complexity: int
    line_count: int


@dataclass(frozen=True)
class ClassMetric:
    target: str
    path: Path
    line: int
    public_methods: int
    line_count: int


@dataclass(frozen=True)
class ModuleMetric:
    target: str
    path: Path
    line: int
    first_party_imports: int


@dataclass(frozen=True)
class Violation:
    rule: str
    path: Path
    line: int
    message: str

    def format(self, project_root: Path) -> str:
        relative = _relative_path(project_root, self.path)
        return f"{relative}:{self.line}: [{self.rule}] {self.message}"


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise TypeError(f"Expected a list of strings, got {value!r}")


def _path_matches(path: str, patterns: Sequence[str]) -> bool:
    return any(_path_matches_pattern(path, pattern) for pattern in patterns)


def _path_matches_pattern(path: str, pattern: str) -> bool:
    """Match POSIX-style globs while treating "/" as a path separator."""
    path_parts = tuple(part for part in path.split("/") if part)
    pattern_parts = tuple(part for part in pattern.split("/") if part)
    memo: dict[tuple[int, int], bool] = {}

    def matches_from(path_index: int, pattern_index: int) -> bool:
        key = (path_index, pattern_index)
        if key in memo:
            return memo[key]
        if pattern_index == len(pattern_parts):
            matched = path_index == len(path_parts)
        elif pattern_parts[pattern_index] == "**":
            matched = matches_from(path_index, pattern_index + 1) or (
                path_index < len(path_parts) and matches_from(path_index + 1, pattern_index)
            )
        else:
            matched = (
                path_index < len(path_parts)
                and fnmatch.fnmatchcase(path_parts[path_index], pattern_parts[pattern_index])
                and matches_from(path_index + 1, pattern_index + 1)
            )
        memo[key] = matched
        return matched

    return matches_from(0, 0)


def _select_sources(
    sources: Sequence[SourceFile],
    *,
    include: Sequence[str],
    exclude: Sequence[str],
) -> list[SourceFile]:
    selected: list[SourceFile] = []
    for source in sources:
        if include and not _path_matches(source.relative_path, include):
            continue
        if exclude and _path_matches(source.relative_path, exclude):
            continue
        selected.append(source)
    return selected


def _module_name(project_root: Path, path: Path) -> str:
    relative = path.relative_to(project_root).with_suffix("")
    return ".".join(relative.parts)


def _discover_source_paths(project_root: Path, roots: Sequence[str]) -> list[Path]:
    paths: list[Path] = []
    for root_name in roots:
        root = project_root / root_name
        if root.is_file() and root.suffix == ".py":
            paths.append(root)
        elif root.is_dir():
            paths.extend(root.rglob("*.py"))
    return sorted({path for path in paths if "__pycache__" not in path.parts})


def _load_sources(project_root: Path, roots: Sequence[str]) -> list[SourceFile]:
    sources: list[SourceFile] = []
    for path in _discover_source_paths(project_root, roots):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        sources.append(
            SourceFile(
                path=path,
                relative_path=_relative_path(project_root, path),
                module_name=_module_name(project_root, path),
                tree=tree,
            )
        )
    return sources


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


def _iter_import_refs(source: SourceFile) -> list[ImportRef]:
    imports: list[ImportRef] = []
    for node in ast.walk(source.tree):
        if isinstance(node, ast.Import):
            imports.extend(ImportRef(alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.extend(ImportRef(target, node.lineno) for target in _resolve_import(source.module_name, node))
    return imports


def _matches_dotted_prefix(target: str, prefix: str) -> bool:
    return target == prefix or target.startswith(f"{prefix}.")


def _is_forbidden_import(
    target: str,
    *,
    forbidden: Sequence[str],
    forbidden_prefixes: Sequence[str],
    allowed: Sequence[str],
    allowed_prefixes: Sequence[str],
) -> bool:
    """Evaluate import boundaries; *_prefixes are raw string prefixes for families like ``world_``."""
    if any(_matches_dotted_prefix(target, prefix) for prefix in allowed):
        return False
    if any(target.startswith(prefix) for prefix in allowed_prefixes):
        return False
    return any(_matches_dotted_prefix(target, prefix) for prefix in forbidden) or any(
        target.startswith(prefix) for prefix in forbidden_prefixes
    )


def _check_import_rules(
    project_root: Path,
    sources: Sequence[SourceFile],
    rules: Sequence[Mapping[str, Any]],
) -> list[Violation]:
    violations: list[Violation] = []
    for rule in rules:
        rule_name = str(rule["name"])
        selected = _select_sources(
            sources,
            include=_as_list(rule.get("include")),
            exclude=_as_list(rule.get("exclude")),
        )
        forbidden = _as_list(rule.get("forbid"))
        forbidden_prefixes = _as_list(rule.get("forbid_prefixes"))
        allowed = _as_list(rule.get("allow"))
        allowed_prefixes = _as_list(rule.get("allow_prefixes"))

        for source in selected:
            for import_ref in _iter_import_refs(source):
                if _is_forbidden_import(
                    import_ref.target,
                    forbidden=forbidden,
                    forbidden_prefixes=forbidden_prefixes,
                    allowed=allowed,
                    allowed_prefixes=allowed_prefixes,
                ):
                    violations.append(
                        Violation(
                            rule=rule_name,
                            path=source.path,
                            line=import_ref.line,
                            message=f"forbidden import {import_ref.target!r}",
                        )
                    )
    return violations


def _expr_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _expr_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _iter_call_refs(source: SourceFile) -> list[CallRef]:
    calls: list[CallRef] = []
    for node in ast.walk(source.tree):
        if not isinstance(node, ast.Call):
            continue
        name = _expr_name(node.func)
        if name:
            calls.append(CallRef(name=name, line=node.lineno))
    return calls


def _matches_call_name(call_name: str, forbidden_name: str) -> bool:
    return call_name == forbidden_name or call_name.endswith(f".{forbidden_name}")


def _check_call_rules(
    project_root: Path,
    sources: Sequence[SourceFile],
    rules: Sequence[Mapping[str, Any]],
) -> list[Violation]:
    """Check direct call expressions; this intentionally does not do data-flow analysis."""
    violations: list[Violation] = []
    for rule in rules:
        rule_name = str(rule["name"])
        selected = _select_sources(
            sources,
            include=_as_list(rule.get("include")),
            exclude=_as_list(rule.get("exclude")),
        )
        forbidden_calls = _as_list(rule.get("forbid_calls"))
        for source in selected:
            for call_ref in _iter_call_refs(source):
                for forbidden_call in forbidden_calls:
                    if _matches_call_name(call_ref.name, forbidden_call):
                        violations.append(
                            Violation(
                                rule=rule_name,
                                path=source.path,
                                line=call_ref.line,
                                message=f"forbidden call {call_ref.name!r}",
                            )
                        )
    return violations


def _resolve_known_module(target: str, known_modules: set[str]) -> str | None:
    if target in known_modules:
        return target
    parts = target.split(".")
    for index in range(len(parts) - 1, 1, -1):
        candidate = ".".join(parts[:index])
        if candidate in known_modules:
            return candidate
    return None


def _check_acyclic_rules(
    sources: Sequence[SourceFile],
    rules: Sequence[Mapping[str, Any]],
) -> list[Violation]:
    violations: list[Violation] = []
    source_by_module = {source.module_name: source for source in sources}

    for rule in rules:
        rule_name = str(rule["name"])
        selected = _select_sources(
            sources,
            include=_as_list(rule.get("include")),
            exclude=_as_list(rule.get("exclude")),
        )
        selected_modules = {source.module_name for source in selected}
        graph = {source.module_name: set[str]() for source in selected}
        for source in selected:
            for import_ref in _iter_import_refs(source):
                target_module = _resolve_known_module(import_ref.target, selected_modules)
                if target_module is not None and target_module != source.module_name:
                    graph[source.module_name].add(target_module)

        for cycle in _find_cycles(graph):
            first = cycle[0]
            violations.append(
                Violation(
                    rule=rule_name,
                    path=source_by_module[first].path,
                    line=1,
                    message=f"import cycle detected: {' -> '.join(cycle + [first])}",
                )
            )
    return violations


def _find_cycles(graph: Mapping[str, set[str]]) -> list[list[str]]:
    index_by_node: dict[str, int] = {}
    lowlink_by_node: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(node: str) -> None:
        index_by_node[node] = len(index_by_node)
        lowlink_by_node[node] = index_by_node[node]
        stack.append(node)
        on_stack.add(node)

        for neighbor in sorted(graph[node]):
            if neighbor not in index_by_node:
                visit(neighbor)
                lowlink_by_node[node] = min(lowlink_by_node[node], lowlink_by_node[neighbor])
            elif neighbor in on_stack:
                lowlink_by_node[node] = min(lowlink_by_node[node], index_by_node[neighbor])

        if lowlink_by_node[node] != index_by_node[node]:
            return
        component: list[str] = []
        while True:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node:
                break
        if len(component) > 1:
            components.append(sorted(component))

    for node in sorted(graph):
        if node not in index_by_node:
            visit(node)
    return components


class _CyclomaticVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.complexity = 1

    def compute(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        for statement in node.body:
            self.visit(statement)
        return self.complexity

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return None

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return None

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self.complexity += len(node.handlers)
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.complexity += 1 + len(node.ifs)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self.complexity += max(1, len(node.cases))
        self.generic_visit(node)


class _CognitiveVisitor(ast.NodeVisitor):
    def __init__(self, function_name: str) -> None:
        self.complexity = 0
        self.function_name = function_name
        self.nesting = 0

    def compute(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        for statement in node.body:
            self.visit(statement)
        return self.complexity

    def _add_nested_flow(self) -> None:
        self.complexity += 1 + self.nesting

    def _visit_nested_body(self, body: Sequence[ast.stmt]) -> None:
        self.nesting += 1
        for statement in body:
            self.visit(statement)
        self.nesting -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return None

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return None

    def visit_If(self, node: ast.If) -> None:
        self._visit_if(node, is_elif=False)

    def _visit_if(self, node: ast.If, *, is_elif: bool) -> None:
        self.complexity += 1 if is_elif else 1 + self.nesting
        self.visit(node.test)
        self._visit_nested_body(node.body)
        if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
            self._visit_if(node.orelse[0], is_elif=True)
        else:
            for statement in node.orelse:
                self.visit(statement)

    def visit_For(self, node: ast.For) -> None:
        self._add_nested_flow()
        self.visit(node.target)
        self.visit(node.iter)
        self._visit_nested_body(node.body)
        for statement in node.orelse:
            self.visit(statement)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._add_nested_flow()
        self.visit(node.target)
        self.visit(node.iter)
        self._visit_nested_body(node.body)
        for statement in node.orelse:
            self.visit(statement)

    def visit_While(self, node: ast.While) -> None:
        self._add_nested_flow()
        self.visit(node.test)
        self._visit_nested_body(node.body)
        for statement in node.orelse:
            self.visit(statement)

    def visit_Try(self, node: ast.Try) -> None:
        for statement in node.body:
            self.visit(statement)
        for handler in node.handlers:
            self._add_nested_flow()
            if handler.type:
                self.visit(handler.type)
            self._visit_nested_body(handler.body)
        for statement in node.orelse + node.finalbody:
            self.visit(statement)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self._add_nested_flow()
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_Break(self, node: ast.Break) -> None:
        self.complexity += 1

    def visit_Continue(self, node: ast.Continue) -> None:
        self.complexity += 1

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self._add_nested_flow()
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self._add_nested_flow()
        self.visit(node.subject)
        self.nesting += 1
        for case in node.cases:
            if case.guard:
                self.visit(case.guard)
            for statement in case.body:
                self.visit(statement)
        self.nesting -= 1

    def visit_Call(self, node: ast.Call) -> None:
        if _expr_name(node.func) == self.function_name:
            self.complexity += 1
        self.generic_visit(node)


class _MetricCollector(ast.NodeVisitor):
    def __init__(self, source: SourceFile) -> None:
        self.source = source
        self.name_stack: list[str] = []
        self.functions: list[FunctionMetric] = []
        self.classes: list[ClassMetric] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        target = self._target(node.name)
        public_methods = sum(
            1
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and not child.name.startswith("_")
        )
        line_count = _line_count(node)
        self.classes.append(
            ClassMetric(
                target=target,
                path=self.source.path,
                line=node.lineno,
                public_methods=public_methods,
                line_count=line_count,
            )
        )
        self.name_stack.append(node.name)
        for child in node.body:
            self.visit(child)
        self.name_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record_function(node)
        self.name_stack.append(node.name)
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.visit(child)
        self.name_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record_function(node)
        self.name_stack.append(node.name)
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.visit(child)
        self.name_stack.pop()

    def _record_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.functions.append(
            FunctionMetric(
                target=self._target(node.name),
                path=self.source.path,
                line=node.lineno,
                cyclomatic_complexity=_CyclomaticVisitor().compute(node),
                cognitive_complexity=_CognitiveVisitor(node.name).compute(node),
                line_count=_line_count(node),
            )
        )

    def _target(self, local_name: str) -> str:
        return f"{self.source.relative_path}::{'.'.join([*self.name_stack, local_name])}"


def _line_count(node: ast.AST) -> int:
    end_line = getattr(node, "end_lineno", None)
    line = getattr(node, "lineno", None)
    if isinstance(end_line, int) and isinstance(line, int):
        return end_line - line + 1
    return 1


def _collect_metrics(
    sources: Sequence[SourceFile],
) -> tuple[list[FunctionMetric], list[ClassMetric], list[ModuleMetric]]:
    function_metrics: list[FunctionMetric] = []
    class_metrics: list[ClassMetric] = []
    module_metrics: list[ModuleMetric] = []

    for source in sources:
        collector = _MetricCollector(source)
        collector.visit(source.tree)
        function_metrics.extend(collector.functions)
        class_metrics.extend(collector.classes)

        first_party_imports = {
            ".".join(import_ref.target.split(".")[:2])
            for import_ref in _iter_import_refs(source)
            if import_ref.target.startswith("fantasy_simulator.")
        }
        module_metrics.append(
            ModuleMetric(
                target=source.relative_path,
                path=source.path,
                line=1,
                first_party_imports=len(first_party_imports),
            )
        )

    return function_metrics, class_metrics, module_metrics


def _override_map(overrides: Sequence[Mapping[str, Any]], metric_name: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for override in overrides:
        if metric_name not in override:
            continue
        target = str(override["target"])
        limit = override[metric_name]
        if type(limit) is not int:
            raise TypeError(f"Override {target!r} has a non-integer {metric_name}")
        values[target] = limit
    return values


def _limit_for(target: str, default_limit: int | None, overrides: Mapping[str, int]) -> int | None:
    return overrides.get(target, default_limit)


def _metric_violation(
    rule: str,
    path: Path,
    line: int,
    target: str,
    metric_name: str,
    value: int,
    limit: int | None,
) -> Violation | None:
    if limit is None or value <= limit:
        return None
    return Violation(
        rule=rule,
        path=path,
        line=line,
        message=f"{target} has {metric_name} {value}, above budget {limit}",
    )


def _stale_override_violation(
    rule: str,
    path: Path,
    line: int,
    target: str,
    metric_name: str,
    value: int,
    default_limit: int | None,
    override_limit: int | None,
) -> Violation | None:
    if default_limit is None or override_limit is None:
        return None
    if override_limit <= default_limit or value > default_limit:
        return None
    return Violation(
        rule=rule,
        path=path,
        line=line,
        message=(
            f"{target} has {metric_name} {value}, now within default budget {default_limit}; "
            f"remove relaxed override {override_limit}"
        ),
    )


def _check_metric_budget(
    sources: Sequence[SourceFile],
    complexity_config: Mapping[str, Any] | None,
) -> list[Violation]:
    if not complexity_config:
        return []

    selected = _select_sources(
        sources,
        include=_as_list(complexity_config.get("include")),
        exclude=_as_list(complexity_config.get("exclude")),
    )
    function_metrics, class_metrics, module_metrics = _collect_metrics(selected)
    overrides = complexity_config.get("overrides", [])
    if not isinstance(overrides, list):
        raise TypeError("complexity.overrides must be a list")

    metric_names = [
        "max_cyclomatic_complexity",
        "max_cognitive_complexity",
        "max_function_lines",
        "max_public_methods",
        "max_class_lines",
        "max_first_party_imports",
    ]
    override_limits = {metric_name: _override_map(overrides, metric_name) for metric_name in metric_names}
    observed_targets_by_budget = {
        "max_cyclomatic_complexity": {metric.target for metric in function_metrics},
        "max_cognitive_complexity": {metric.target for metric in function_metrics},
        "max_function_lines": {metric.target for metric in function_metrics},
        "max_public_methods": {metric.target for metric in class_metrics},
        "max_class_lines": {metric.target for metric in class_metrics},
        "max_first_party_imports": {metric.target for metric in module_metrics},
    }

    violations: list[Violation] = []
    violations.extend(_unused_override_violations(overrides, observed_targets_by_budget, selected))
    for function_metric in function_metrics:
        checks = [
            ("cyclomatic complexity", function_metric.cyclomatic_complexity, "max_cyclomatic_complexity"),
            ("cognitive complexity", function_metric.cognitive_complexity, "max_cognitive_complexity"),
            ("function lines", function_metric.line_count, "max_function_lines"),
        ]
        for label, value, config_key in checks:
            default_limit = _optional_int(complexity_config.get(config_key))
            override_limit = override_limits[config_key].get(function_metric.target)
            stale_violation = _stale_override_violation(
                "stale_complexity_override",
                function_metric.path,
                function_metric.line,
                function_metric.target,
                label,
                value,
                default_limit,
                override_limit,
            )
            if stale_violation:
                violations.append(stale_violation)
            limit = _limit_for(
                function_metric.target,
                default_limit,
                override_limits[config_key],
            )
            violation = _metric_violation(
                "complexity_budget",
                function_metric.path,
                function_metric.line,
                function_metric.target,
                label,
                value,
                limit,
            )
            if violation:
                violations.append(violation)

    for class_metric in class_metrics:
        checks = [
            ("public method count", class_metric.public_methods, "max_public_methods"),
            ("class lines", class_metric.line_count, "max_class_lines"),
        ]
        for label, value, config_key in checks:
            default_limit = _optional_int(complexity_config.get(config_key))
            override_limit = override_limits[config_key].get(class_metric.target)
            stale_violation = _stale_override_violation(
                "stale_complexity_override",
                class_metric.path,
                class_metric.line,
                class_metric.target,
                label,
                value,
                default_limit,
                override_limit,
            )
            if stale_violation:
                violations.append(stale_violation)
            limit = _limit_for(
                class_metric.target,
                default_limit,
                override_limits[config_key],
            )
            violation = _metric_violation(
                "complexity_budget",
                class_metric.path,
                class_metric.line,
                class_metric.target,
                label,
                value,
                limit,
            )
            if violation:
                violations.append(violation)

    for module_metric in module_metrics:
        config_key = "max_first_party_imports"
        default_limit = _optional_int(complexity_config.get(config_key))
        override_limit = override_limits[config_key].get(module_metric.target)
        stale_violation = _stale_override_violation(
            "stale_complexity_override",
            module_metric.path,
            module_metric.line,
            module_metric.target,
            "first-party import count",
            module_metric.first_party_imports,
            default_limit,
            override_limit,
        )
        if stale_violation:
            violations.append(stale_violation)
        limit = _limit_for(module_metric.target, default_limit, override_limits[config_key])
        violation = _metric_violation(
            "complexity_budget",
            module_metric.path,
            module_metric.line,
            module_metric.target,
            "first-party import count",
            module_metric.first_party_imports,
            limit,
        )
        if violation:
            violations.append(violation)

    return violations


def _unused_override_violations(
    overrides: Sequence[Mapping[str, Any]],
    observed_targets_by_budget: Mapping[str, set[str]],
    selected: Sequence[SourceFile],
) -> list[Violation]:
    path = selected[0].path if selected else PROJECT_ROOT / "architecture_guard.json"
    violations: list[Violation] = []
    for override in overrides:
        target = str(override["target"])
        for budget_key, observed_targets in observed_targets_by_budget.items():
            if budget_key not in override or target in observed_targets:
                continue
            violations.append(
                Violation(
                    rule="unused_complexity_override",
                    path=path,
                    line=1,
                    message=(
                        f"complexity override {budget_key} target {target!r} "
                        "does not match any observed metric target"
                    ),
                )
            )
    return violations


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is int:
        return value
    raise TypeError(f"Expected an integer or null, got {value!r}")


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("architecture guard config must be a JSON object")
    validate_config(data)
    return data


def validate_config(config: Mapping[str, Any]) -> None:
    complexity_config = config.get("complexity")
    if complexity_config is None:
        return
    if not isinstance(complexity_config, Mapping):
        raise TypeError("complexity must be a JSON object")
    overrides = complexity_config.get("overrides", [])
    if not isinstance(overrides, list) or not all(isinstance(override, Mapping) for override in overrides):
        raise TypeError("complexity.overrides must be a list of JSON objects")
    for key in BUDGET_OVERRIDE_KEYS:
        _optional_int(complexity_config.get(key))
    for override in overrides:
        _validate_complexity_override(override)


def _validate_complexity_override(override: Mapping[str, Any]) -> None:
    target = override.get("target")
    if not isinstance(target, str) or not target.strip():
        raise TypeError("complexity override requires a non-empty target")
    if not any(key in override for key in BUDGET_OVERRIDE_KEYS):
        raise TypeError(f"complexity override for {target!r} must define at least one budget")
    reason = override.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise TypeError(f"complexity override for {target!r} requires a non-empty reason")
    owner = override.get("owner")
    if not isinstance(owner, str) or not owner.strip():
        raise TypeError(f"complexity override for {target!r} requires a non-empty owner")
    removal_condition = override.get("removal_condition")
    if not isinstance(removal_condition, str) or not removal_condition.strip():
        raise TypeError(f"complexity override for {target!r} requires a non-empty removal_condition")
    for key in BUDGET_OVERRIDE_KEYS:
        if key in override:
            _optional_int(override[key])


def run_checks(project_root: Path, config: Mapping[str, Any]) -> list[Violation]:
    source_roots = _as_list(config.get("source_roots"))
    if not source_roots:
        raise ValueError("architecture guard config requires source_roots")

    sources = _load_sources(project_root, source_roots)
    violations: list[Violation] = []
    violations.extend(
        _check_import_rules(
            project_root,
            sources,
            _mapping_list(config.get("import_boundary_rules")),
        )
    )
    violations.extend(
        _check_call_rules(
            project_root,
            sources,
            _mapping_list(config.get("call_boundary_rules")),
        )
    )
    violations.extend(
        _check_acyclic_rules(
            sources,
            _mapping_list(config.get("acyclic_package_rules")),
        )
    )
    complexity_config = config.get("complexity")
    if complexity_config is not None and not isinstance(complexity_config, Mapping):
        raise TypeError("complexity must be a JSON object")
    violations.extend(_check_metric_budget(sources, complexity_config))
    return violations


def _mapping_list(value: object) -> list[Mapping[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, Mapping) for item in value):
        raise TypeError(f"Expected a list of JSON objects, got {value!r}")
    return value


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to architecture guard JSON config.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format for violations.",
    )
    return parser.parse_args(argv)


def _violations_as_json(project_root: Path, violations: Iterable[Violation]) -> str:
    return json.dumps(
        [
            {
                "rule": violation.rule,
                "path": _relative_path(project_root, violation.path),
                "line": violation.line,
                "message": violation.message,
            }
            for violation in violations
        ],
        ensure_ascii=False,
        indent=2,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = Path(args.config)
    project_root = (
        PROJECT_ROOT
        if config_path.resolve() == DEFAULT_CONFIG_PATH.resolve()
        else config_path.resolve().parent
    )
    violations = run_checks(project_root, load_config(config_path))

    if args.format == "json":
        print(_violations_as_json(project_root, violations))
    elif violations:
        for violation in violations:
            print(violation.format(project_root))
    else:
        print("[architecture-guard] passed")

    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
