from pathlib import Path

import pytest

from classcorpus.database import Database
from classcorpus.indexer import sync_course
from classcorpus.record_text import MAX_CHUNK_CHARS, read_record_text
from tests.fixtures.make_fixtures import make_pdf_fixture


@pytest.fixture
def chunked_course(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Database:
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "Algorithms"
    root.mkdir()
    make_pdf_fixture(root / "handout.pdf")
    database = Database(tmp_path / "index.sqlite3")
    database.initialize()
    assert sync_course(database, "Algorithms", root).indexed == 1
    return database


def test_raw_text_chunks_reconstruct_complete_record_without_gaps(
    chunked_course: Database,
):
    expected = str(
        chunked_course.connection.execute(
            """
            SELECT slides.raw_text
            FROM slides
            JOIN source_files ON source_files.id = slides.source_file_id
            WHERE source_files.relative_path = 'handout.pdf'
              AND slides.ordinal = 1
            """
        ).fetchone()["raw_text"]
    )
    chunks: list[str] = []
    offset = 0
    while True:
        chunk = read_record_text(
            chunked_course,
            course="Algorithms",
            source_file="handout.pdf",
            ordinal=1,
            field="raw_text",
            offset=offset,
            limit=7_000,
        )
        chunks.append(chunk.text)
        assert chunk.offset == offset
        assert chunk.returned_chars <= 7_000
        assert chunk.citation == "[Algorithms, handout.pdf, Page 1]"
        if not chunk.has_more:
            assert chunk.next_offset is None
            break
        assert chunk.next_offset == offset + chunk.returned_chars
        offset = chunk.next_offset

    assert "".join(chunks) == expected
    assert chunk.total_chars == len(expected)


def test_searchable_chunk_is_bounded_and_labels_evidence(
    chunked_course: Database,
):
    chunk = read_record_text(
        chunked_course,
        course="Algorithms",
        source_file="handout.pdf",
        ordinal=2,
        limit=80,
    )

    assert chunk.field == "searchable"
    assert chunk.text.startswith("Title:\nDiagram")
    assert chunk.returned_chars <= 80


def test_default_chunk_is_two_thousand_characters(chunked_course: Database):
    chunk = read_record_text(
        chunked_course,
        course="Algorithms",
        source_file="handout.pdf",
        ordinal=1,
        field="raw_text",
    )

    assert chunk.returned_chars == 2_000
    assert chunk.next_offset == 2_000


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"ordinal": 0}, "ordinal"),
        ({"offset": -1}, "offset"),
        ({"limit": 0}, "limit"),
        ({"limit": MAX_CHUNK_CHARS + 1}, "limit"),
        ({"field": "missing"}, "field"),
        ({"offset": 1_000_000}, "offset exceeds"),
    ],
)
def test_record_chunk_validation(
    chunked_course: Database,
    kwargs: dict[str, object],
    message: str,
):
    arguments = {
        "course": "Algorithms",
        "source_file": "handout.pdf",
        "ordinal": 1,
        **kwargs,
    }

    with pytest.raises(ValueError, match=message):
        read_record_text(chunked_course, **arguments)


def test_missing_record_is_explicit(chunked_course: Database):
    with pytest.raises(ValueError, match="record not found"):
        read_record_text(
            chunked_course,
            course="Algorithms",
            source_file="missing.pdf",
            ordinal=1,
        )
