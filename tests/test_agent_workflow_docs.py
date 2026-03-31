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
    assert "Plan anchor" in text
    assert "synchronized with actual progress" in text


def test_plan_and_implementation_context_require_progress_sync():
    plan_text = _read("docs/implementation_plan.md")
    implementation = _read("docs/contexts/implementation.md")
    lessons = _read("docs/agent_lessons.md")

    assert "サブエージェント" in plan_text
    assert "委譲" in plan_text
    # Guard the specific new rules in §2.2, not just pre-existing keywords
    assert "同じ変更で同期する" in plan_text
    assert "PR 状態" in plan_text
    assert "Sync roadmap/status text" in implementation
    assert "well-bounded subagents" in lessons
    assert "synchronized with actual progress" in lessons


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
    assert "progress text sync status" in template
    assert all(path.stem[:4].isdigit() for path in dated_notes)
