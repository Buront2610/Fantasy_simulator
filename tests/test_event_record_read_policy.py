"""Guardrails for canonical read paths (event_records-first)."""

from pathlib import Path


def test_new_view_model_layer_does_not_reference_legacy_history():
    text = Path("fantasy_simulator/ui/view_models.py").read_text(encoding="utf-8")
    assert ".history" not in text


def test_new_view_model_layer_does_not_reference_event_log():
    text = Path("fantasy_simulator/ui/view_models.py").read_text(encoding="utf-8")
    assert "event_log" not in text
