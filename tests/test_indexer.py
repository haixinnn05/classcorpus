from pathlib import Path

import pytest

from classcorpus.database import Database
from classcorpus.indexer import fingerprint, sync_course
from classcorpus.models import SlideRecord
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


def test_moved_course_refreshes_source_paths_without_reprocessing(
    course_fixture: Path,
    database: Database,
):
    sync_course(database, "Algorithms", course_fixture)
    moved_root = course_fixture.parent / "Algorithms-Moved"
    course_fixture.rename(moved_root)

    report = sync_course(database, "Algorithms", moved_root)

    assert report.indexed == 0
    assert report.skipped == 2
    assert {
        Path(row["source_path"]).parent
        for row in database.connection.execute(
            "SELECT source_path FROM source_files"
        )
    } == {moved_root.resolve()}


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


def test_fingerprint_failure_does_not_stop_other_sources(
    course_fixture: Path,
    database: Database,
    monkeypatch: pytest.MonkeyPatch,
):
    original_fingerprint = fingerprint

    def flaky_fingerprint(path: Path):
        if path.name == "lecture-1.pdf":
            raise PermissionError("source is locked")
        return original_fingerprint(path)

    monkeypatch.setattr("classcorpus.indexer.fingerprint", flaky_fingerprint)

    report = sync_course(database, "Algorithms", course_fixture)

    assert report.indexed == 1
    assert report.failed == 1
    assert report.failures[0]["type"] == "PermissionError"
    assert report.failures[0]["path"].endswith("lecture-1.pdf")
    assert database.slide_count("Algorithms") == 2
    assert database.source_health("Algorithms").failed == 1
    assert database.source_failures("Algorithms")[0]["source_file"] == "lecture-1.pdf"


def test_missing_pptx_renderer_returns_actionable_warning(
    course_fixture: Path,
    database: Database,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr("classcorpus.parsers.shutil.which", lambda _: None)

    report = sync_course(database, "Algorithms", course_fixture)

    warning = next(
        item for item in report.warnings if item["path"].endswith("lecture-2.pptx")
    )
    assert warning["type"] == "renderer_unavailable"
    assert "LibreOffice" in warning["message"]
    generation_dirs = set(
        (course_fixture.parent / "data" / "renders").rglob("generation-*")
    )
    referenced_dirs = {
        Path(row["render_path"]).parent
        for row in database.connection.execute(
            "SELECT render_path FROM slides WHERE render_path IS NOT NULL"
        )
    }
    assert generation_dirs == referenced_dirs


def test_removed_source_is_pruned_from_index(
    course_fixture: Path,
    database: Database,
):
    sync_course(database, "Algorithms", course_fixture)
    render_paths = [
        Path(row["render_path"])
        for row in database.connection.execute(
            """
            SELECT slides.render_path
            FROM slides
            JOIN source_files ON source_files.id = slides.source_file_id
            WHERE source_files.relative_path = 'lecture-2.pptx'
              AND slides.render_path IS NOT NULL
            """
        )
    ]
    (course_fixture / "lecture-2.pptx").unlink()

    report = sync_course(database, "Algorithms", course_fixture)

    assert report.skipped == 1
    assert database.slide_count("Algorithms") == 2
    assert database.connection.execute(
        "SELECT COUNT(*) FROM source_files"
    ).fetchone()[0] == 1
    assert all(not path.exists() for path in render_paths)


def test_render_cleanup_failure_is_a_warning_and_sync_continues(
    course_fixture: Path,
    database: Database,
    monkeypatch: pytest.MonkeyPatch,
):
    sync_course(database, "Algorithms", course_fixture)
    (course_fixture / "lecture-2.pptx").unlink()
    monkeypatch.setattr(
        "classcorpus.database.shutil.rmtree",
        lambda _: (_ for _ in ()).throw(OSError("cache is busy")),
    )

    report = sync_course(database, "Algorithms", course_fixture)

    assert report.failed == 0
    assert report.skipped == 1
    warning = next(
        item for item in report.warnings if item["type"] == "cache_cleanup_failed"
    )
    assert "cache is busy" in warning["message"]
    assert database.slide_count("Algorithms") == 2


def test_changed_source_removes_superseded_render_cache(
    course_fixture: Path,
    database: Database,
):
    sync_course(database, "Algorithms", course_fixture)
    old_paths = [
        Path(row["render_path"])
        for row in database.connection.execute(
            """
            SELECT slides.render_path
            FROM slides
            JOIN source_files ON source_files.id = slides.source_file_id
            WHERE source_files.relative_path = 'lecture-1.pdf'
            """
        )
    ]
    pdf = course_fixture / "lecture-1.pdf"
    with pdf.open("ab") as stream:
        stream.write(b"\n")

    report = sync_course(database, "Algorithms", course_fixture)

    assert report.indexed == 1
    assert all(not path.exists() for path in old_paths)
    assert all(
        Path(row["render_path"]).is_file()
        for row in database.connection.execute(
            """
            SELECT slides.render_path
            FROM slides
            JOIN source_files ON source_files.id = slides.source_file_id
            WHERE source_files.relative_path = 'lecture-1.pdf'
            """
        )
    )


def test_failed_same_version_retry_preserves_previous_render_cache(
    tmp_path: Path,
    database: Database,
    monkeypatch: pytest.MonkeyPatch,
):
    root = tmp_path / "Algorithms"
    root.mkdir()
    source = make_pdf_fixture(root / "lecture.pdf")
    assert sync_course(database, "Algorithms", root).indexed == 1
    old_paths = [
        Path(row["render_path"])
        for row in database.connection.execute(
            "SELECT render_path FROM slides ORDER BY ordinal"
        )
    ]
    old_bytes = [path.read_bytes() for path in old_paths]

    with database.connection:
        database.connection.execute(
            """
            UPDATE source_files
            SET status = 'failed', error_message = 'force retry'
            WHERE relative_path = 'lecture.pdf'
            """
        )

    def fail_after_writing(_source: Path, render_dir: Path):
        render_dir.mkdir(parents=True, exist_ok=True)
        (render_dir / "page-0001.png").write_bytes(b"corrupt replacement")
        raise RuntimeError("new parser failed")

    monkeypatch.setattr("classcorpus.indexer.parse_source", fail_after_writing)

    report = sync_course(database, "Algorithms", root)
    retained_paths = [
        Path(row["render_path"])
        for row in database.connection.execute(
            "SELECT render_path FROM slides ORDER BY ordinal"
        )
    ]

    assert report.failed == 1
    assert retained_paths == old_paths
    assert [path.read_bytes() for path in retained_paths] == old_bytes
    assert source.is_file()


def test_image_only_records_are_reported_explicitly(
    tmp_path: Path,
    database: Database,
    monkeypatch: pytest.MonkeyPatch,
):
    root = tmp_path / "ImageOnly"
    root.mkdir()
    source = root / "diagram.pdf"
    source.write_bytes(b"placeholder")
    render = tmp_path / "data" / "renders" / "diagram.png"
    render.parent.mkdir(parents=True)
    render.write_bytes(b"png")
    monkeypatch.setattr(
        "classcorpus.indexer.parse_source",
        lambda *_: [
            SlideRecord(
                ordinal=1,
                kind="page",
                title="",
                body_text="",
                speaker_notes="",
                render_path=str(render),
            )
        ],
    )

    report = sync_course(database, "ImageOnly", root)

    assert report.indexed == 1
    warning = next(item for item in report.warnings if item["type"] == "image_only")
    assert warning["ordinal"] == "1"
    assert "visual analysis" in warning["message"]
