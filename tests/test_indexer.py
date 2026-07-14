from pathlib import Path

import pytest

from classcorpus.database import Database
from classcorpus.indexer import fingerprint, sync_course
from tests.fixtures.make_fixtures import make_pdf_fixture, make_pptx_fixture


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "data"))
    db = Database(tmp_path / "index.sqlite3")
    db.initialize()
    return db


@pytest.fixture
def course_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "Algorithms"
    root.mkdir()
    make_pdf_fixture(root / "lecture-1.pdf")
    make_pptx_fixture(root / "lecture-2.pptx")
    return root


def test_fingerprint_is_stable_until_content_changes(tmp_path: Path):
    source = tmp_path / "lecture.pdf"
    source.write_bytes(b"first")
    first = fingerprint(source)
    second = fingerprint(source)
    source.write_bytes(b"second")
    changed = fingerprint(source)

    assert first.sha256 == second.sha256
    assert first.parser_version == "1"
    assert changed.sha256 != first.sha256


def test_second_sync_skips_unchanged_files(course_fixture: Path, database: Database):
    first = sync_course(database, "Algorithms", course_fixture)
    second = sync_course(database, "Algorithms", course_fixture)

    assert first.indexed == 2
    assert first.failed == 0
    assert second.indexed == 0
    assert second.skipped == 2
    assert database.slide_count("Algorithms") == 4


def test_only_changed_file_is_reprocessed(course_fixture: Path, database: Database):
    sync_course(database, "Algorithms", course_fixture)
    pdf = course_fixture / "lecture-1.pdf"
    make_pdf_fixture(pdf)
    with pdf.open("ab") as stream:
        stream.write(b"\n")

    report = sync_course(database, "Algorithms", course_fixture)

    assert report.indexed == 1
    assert report.skipped == 1
    assert report.failed == 0


def test_corrupt_file_does_not_remove_valid_records(
    course_fixture: Path, database: Database
):
    sync_course(database, "Algorithms", course_fixture)
    original_count = database.slide_count("Algorithms")
    pdf = course_fixture / "lecture-1.pdf"
    pdf.write_bytes(b"not a pdf")

    report = sync_course(database, "Algorithms", course_fixture)

    assert report.failed == 1
    assert report.indexed == 0
    assert report.skipped == 1
    assert report.failures[0]["path"].endswith("lecture-1.pdf")
    assert database.slide_count("Algorithms") == original_count
