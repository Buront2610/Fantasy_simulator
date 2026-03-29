"""Checks for operational docs added to support agent workflows."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def test_context_docs_exist_and_stay_short():
    implementation = _read("docs/contexts/implementation.md")
    review = _read("docs/contexts/review.md")

    assert "Implementation Context" in implementation
    assert "Review Context" in review
    assert len(implementation.splitlines()) < 40
    assert len(review.splitlines()) < 35


def test_subagent_contract_contains_required_sections():
    text = _read("docs/subagent_contract.md")
    for required in ("Required Inputs", "Research", "Plan", "Implement", "Review"):
        assert required in text


def test_agent_lessons_and_handoff_template_exist():
    lessons = _read("docs/agent_lessons.md")
    template = _read("docs/session_handoffs/TEMPLATE.md")
    handoff_dir = PROJECT_ROOT / "docs" / "session_handoffs"
    dated_notes = [
        path for path in handoff_dir.glob("*.md")
        if path.name != "TEMPLATE.md"
    ]

    assert "Recurrent Pitfalls" in lessons
    assert "Confirmed Facts" in template
    assert all(path.stem[:4].isdigit() for path in dated_notes)
