from pathlib import Path

import pytest

from classcorpus.citations import format_citation
from classcorpus.database import Database
from classcorpus.indexer import sync_course
from classcorpus.search import SearchResult, search
from tests.fixtures.make_fixtures import make_pdf_fixture, make_pptx_fixture


@pytest.fixture
def indexed_course(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "Algorithms"
    root.mkdir()
    make_pdf_fixture(root / "handout.pdf")
    make_pptx_fixture(root / "Lecture08.pptx")
    database = Database(tmp_path / "index.sqlite3")
    database.initialize()
    report = sync_course(database, "Algorithms", root)
    assert report.indexed == 2
    return database


def test_search_returns_ranked_page_metadata(indexed_course: Database):
    results = search(indexed_course, "negative edges", course="Algorithms")

    assert results
    assert results[0].source_file == "handout.pdf"
    assert results[0].ordinal == 2
    assert results[0].kind == "page"
    assert Path(results[0].source_path).is_absolute()
    assert "Bellman-Ford" in results[0].body_text


def test_search_finds_speaker_notes_and_table_text(indexed_course: Database):
    notes = search(indexed_course, "example Fibonacci", course="Algorithms")
    table = search(indexed_course, "Problem State", course="Algorithms")

    assert notes[0].source_file == "Lecture08.pptx"
    assert notes[0].ordinal == 2
    assert table[0].ordinal == 2


def test_search_filters_by_source_file_and_ordinal(indexed_course: Database):
    results = search(
        indexed_course,
        "dynamic programming Fibonacci",
        course="Algorithms",
        source_file="Lecture08.pptx",
        ordinal=2,
    )

    assert [(result.source_file, result.ordinal) for result in results] == [
        ("Lecture08.pptx", 2)
    ]
    assert search(
        indexed_course,
        "Bellman-Ford",
        course="Algorithms",
        source_file="Lecture08.pptx",
    ) == []


def test_search_rejects_blank_query(indexed_course: Database):
    with pytest.raises(ValueError, match="query must not be blank"):
        search(indexed_course, "   ")


def test_search_rejects_non_positive_ordinal(indexed_course: Database):
    with pytest.raises(ValueError, match="ordinal must be at least 1"):
        search(indexed_course, "memoization", ordinal=0)


def test_failed_refresh_marks_retained_results_as_stale(indexed_course: Database):
    row = indexed_course.connection.execute(
        """
        SELECT source_path FROM source_files
        WHERE relative_path = 'handout.pdf'
        """
    ).fetchone()
    Path(row["source_path"]).write_bytes(b"not a pdf")
    report = sync_course(
        indexed_course,
        "Algorithms",
        Path(row["source_path"]).parent,
    )

    results = search(indexed_course, "negative edges", course="Algorithms")

    assert report.failed == 1
    assert results[0].source_status == "failed"
    assert results[0].source_error


def test_citation_uses_slide_or_page():
    slide = SearchResult(
        slide_id=1,
        course="Algorithms",
        source_file="Lecture08.pptx",
        source_path="/courses/Algorithms/Lecture08.pptx",
        source_status="ready",
        source_error=None,
        ordinal=27,
        kind="slide",
        title="Dynamic Programming",
        body_text="Memoization",
        speaker_notes="",
        visual_description=None,
        render_path=None,
        vision_status="pending",
        snippet="Memoization",
        score=1.0,
    )
    page = SearchResult(
        slide_id=2,
        course="Algorithms",
        source_file="handout.pdf",
        source_path="/courses/Algorithms/handout.pdf",
        source_status="ready",
        source_error=None,
        ordinal=3,
        kind="page",
        title="Shortest Paths",
        body_text="Bellman-Ford",
        speaker_notes="",
        visual_description=None,
        render_path=None,
        vision_status="pending",
        snippet="Bellman-Ford",
        score=1.0,
    )

    assert format_citation(slide) == "[Algorithms, Lecture08.pptx, Slide 27]"
    assert format_citation(page) == "[Algorithms, handout.pdf, Page 3]"
