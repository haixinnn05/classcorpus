from pathlib import Path

import pytest

from classcorpus.database import Database, remove_course_data
from classcorpus.indexer import sync_course
from tests.fixtures.make_fixtures import make_pdf_fixture


def test_remove_course_deletes_generated_data_not_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    data_root = tmp_path / "state"
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(data_root))
    source_root = tmp_path / "Algorithms"
    source_root.mkdir()
    source = make_pdf_fixture(source_root / "handout.pdf")
    original = source.read_bytes()
    database = Database()
    database.initialize()
    assert sync_course(database, "Algorithms", source_root).indexed == 1
    render_paths = [
        Path(row["render_path"])
        for row in database.connection.execute(
            "SELECT render_path FROM slides WHERE render_path IS NOT NULL"
        )
    ]
    assert render_paths and all(path.is_file() for path in render_paths)

    assert remove_course_data(database, "Algorithms", confirmed=False) is False
    assert database.slide_count("Algorithms") == 2
    assert remove_course_data(database, "Algorithms", confirmed=True) is True

    assert source.read_bytes() == original
    assert all(not path.exists() for path in render_paths)
    assert database.slide_count("Algorithms") == 0


def test_remove_course_rejects_generated_path_outside_data_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "state"))
    database = Database()
    database.initialize()
    course = database.upsert_course("Algorithms", tmp_path / "course")
    outside = tmp_path / "do-not-delete.png"
    outside.write_bytes(b"keep")
    with database.connection:
        source_id = database.connection.execute(
            """
            INSERT INTO source_files(
                course_id, relative_path, source_path, size, mtime_ns,
                sha256, parser_version, status
            ) VALUES (?, 'x.pdf', ?, 1, 1, 'hash', '1', 'ready')
            """,
            (course.id, str(tmp_path / "course" / "x.pdf")),
        ).lastrowid
        database.connection.execute(
            """
            INSERT INTO slides(
                source_file_id, ordinal, kind, title, body_text,
                speaker_notes, render_path
            ) VALUES (?, 1, 'page', '', '', '', ?)
            """,
            (source_id, str(outside)),
        )

    with pytest.raises(ValueError, match="outside ClassCorpus data directory"):
        remove_course_data(database, "Algorithms", confirmed=True)

    assert outside.read_bytes() == b"keep"
