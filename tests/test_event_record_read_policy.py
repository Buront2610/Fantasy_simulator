"""Guardrails for canonical read paths (event_records-first)."""

import ast
from pathlib import Path


PRODUCTION_ROOT = Path("fantasy_simulator")


def test_new_view_model_layer_does_not_reference_legacy_history():
    text = Path("fantasy_simulator/ui/view_models.py").read_text(encoding="utf-8")
    assert ".history" not in text


def test_new_view_model_layer_does_not_reference_event_log():
    text = Path("fantasy_simulator/ui/view_models.py").read_text(encoding="utf-8")
    assert "event_log" not in text


def test_production_code_does_not_call_display_only_log_event_adapter():
    offenders = []
    for path in PRODUCTION_ROOT.rglob("*.py"):
        if path.name == "world_event_log_api.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "log_event":
                offenders.append(f"{path}:{node.lineno}")

    assert offenders == []
