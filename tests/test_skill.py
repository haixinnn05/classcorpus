from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def skill_text() -> str:
    return (ROOT / "SKILL.md").read_text(encoding="utf-8")


def test_skill_requires_retrieval_before_course_answers(skill_text: str):
    assert "search_lectures.py" in skill_text
    assert "Do not answer a course-specific claim before searching" in skill_text
    assert "Cite every course-derived factual claim" in skill_text


def test_skill_forbids_application_surfaces(skill_text: str):
    forbidden = ("web server", "custom chatbot", "hosted backend")
    assert all(f"Do not create a {item}" in skill_text for item in forbidden)


def test_skill_documents_visual_consent_and_storage(skill_text: str):
    assert "Ask for confirmation before visual analysis" in skill_text
    assert "vision_queue.py" in skill_text
    assert "store_visual_description.py" in skill_text


def test_skill_covers_all_study_workflows(skill_text: str):
    required = (
        "summary",
        "flashcards",
        "practice exam",
        "cheat sheet",
        "study plan",
        "cross-lecture comparison",
    )
    assert all(term in skill_text.lower() for term in required)


def test_skill_is_concise_and_references_detailed_guides(skill_text: str):
    assert len(skill_text.splitlines()) < 500
    assert "references/record-schema.md" in skill_text
    assert "references/citation-rules.md" in skill_text
    assert "references/study-workflows.md" in skill_text
