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


def test_skill_uses_repository_python_and_exhaustive_reader(skill_text: str):
    assert ".venv/bin/python" in skill_text
    assert r".venv\Scripts\python.exe" in skill_text
    assert "read_lectures.py" in skill_text
    assert "has_more" in skill_text
    assert "next_cursor" in skill_text
    assert "all/every/whole" in skill_text


def test_skill_discloses_extraction_limits(skill_text: str):
    assert "review-needed" in skill_text
    assert "embedded images" in skill_text
    assert "full-slide rendering" in skill_text
    assert "export" in skill_text.lower()
    assert "PDF" in skill_text


def test_public_docs_have_no_prohibited_converter_references():
    paths = [
        ROOT / "README.md",
        ROOT / "SKILL.md",
        *sorted((ROOT / "references").glob("*.md")),
    ]
    prohibited = (
        "libre" + "office",
        "sof" + "fice",
        "uno" + "conv",
    )

    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        assert all(term not in text for term in prohibited), path


def test_open_source_repository_artifacts_exist():
    required = (
        "docs/architecture.md",
        "docs/privacy.md",
        "ROADMAP.md",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        "examples/README.md",
    )

    assert all((ROOT / relative_path).is_file() for relative_path in required)


def test_reference_docs_define_exhaustive_read_contract():
    schema = (ROOT / "references/record-schema.md").read_text(encoding="utf-8")
    workflows = (ROOT / "references/study-workflows.md").read_text(
        encoding="utf-8"
    )

    assert "read_lectures.py" in schema
    assert "total_records" in schema
    assert "raw_text" in schema
    assert "visual_assets" in schema
    assert "read_lectures.py" in workflows
    assert "has_more" in workflows


def test_skill_and_schema_define_powerpoint_review_contract(skill_text: str):
    schema = (ROOT / "references/record-schema.md").read_text(encoding="utf-8")

    assert "review_powerpoint.py" in skill_text
    assert "next_offset" in skill_text
    assert "review_powerpoint.py" in schema
    assert "asset-reviewed-layout-unverified" in schema
    assert "pdf-export-required" in schema


def test_skill_and_schema_define_local_ocr_confidence(skill_text: str):
    schema = (ROOT / "references/record-schema.md").read_text(encoding="utf-8")

    assert "run_ocr.py" in skill_text
    assert "ocr_confidence" in skill_text
    assert "uncalibrated" in skill_text
    assert "run_ocr.py" in schema
    assert "PartialOCRFailure" in schema
