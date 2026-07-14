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


def test_remove_course_preserves_render_cache_referenced_by_another_course(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "state"))
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first = make_pdf_fixture(first_root / "shared.pdf")
    (second_root / "shared.pdf").write_bytes(first.read_bytes())
    database = Database()
    database.initialize()
    assert sync_course(database, "CS 101", first_root).indexed == 1
    first_paths = {
        Path(row["render_path"])
        for row in database.connection.execute(
            """
            SELECT slides.render_path
            FROM slides
            JOIN source_files ON source_files.id = slides.source_file_id
            JOIN courses ON courses.id = source_files.course_id
            WHERE courses.name = 'CS 101'
            """
        )
    }
    assert sync_course(database, "CS-101", second_root).indexed == 1
    second_paths = {
        Path(row["render_path"])
        for row in database.connection.execute(
            """
            SELECT slides.render_path
            FROM slides
            JOIN source_files ON source_files.id = slides.source_file_id
            JOIN courses ON courses.id = source_files.course_id
            WHERE courses.name = 'CS-101'
            """
        )
    }
    assert first_paths.isdisjoint(second_paths)
    assert second_paths and all(path.is_file() for path in second_paths)

    assert remove_course_data(database, "CS 101", confirmed=True) is True

    assert database.slide_count("CS-101") == 2
    assert all(not path.exists() for path in first_paths)
    assert all(path.is_file() for path in second_paths)


def test_cleanup_resolution_failure_is_warning_and_preserves_candidates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    data_root = tmp_path / "state"
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(data_root))
    candidate = data_root / "renders" / "algorithms" / "hash"
    candidate.mkdir(parents=True)
    database = Database()
    database.initialize()
    course = database.upsert_course("Algorithms", tmp_path / "course")
    with database.connection:
        source_id = database.connection.execute(
            """
            INSERT INTO source_files(
                course_id, relative_path, source_path, size, mtime_ns,
                sha256, parser_version, status
            ) VALUES (?, 'bad.pdf', ?, 1, 1, 'hash', '1', 'ready')
            """,
            (course.id, str(tmp_path / "course" / "bad.pdf")),
        ).lastrowid
        database.connection.execute(
            """
            INSERT INTO slides(
                source_file_id, ordinal, kind, title, body_text,
                speaker_notes, render_path
            ) VALUES (?, 1, 'page', '', '', '', ?)
            """,
            (source_id, "\0"),
        )

    warnings = database.cleanup_render_directories({candidate})

    assert warnings[0]["type"] == "cache_cleanup_failed"
    assert candidate.is_dir()


def test_partial_cache_failure_removes_records_and_keeps_retry_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "state"))
    root = tmp_path / "Algorithms"
    root.mkdir()
    make_pdf_fixture(root / "first.pdf")
    make_pdf_fixture(root / "second.pdf")
    database = Database()
    database.initialize()
    assert sync_course(database, "Algorithms", root).indexed == 2
    calls = 0
    original_rmtree = __import__("shutil").rmtree

    def fail_second(path: Path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("second cache is busy")
        original_rmtree(path)

    monkeypatch.setattr("classcorpus.database.shutil.rmtree", fail_second)

    with pytest.raises(OSError, match="second cache is busy"):
        remove_course_data(database, "Algorithms", confirmed=True)

    assert database.slide_count("Algorithms") == 0
    assert database.connection.execute(
        "SELECT COUNT(*) FROM pending_deletions"
    ).fetchone()[0] == 1

    monkeypatch.setattr("classcorpus.database.shutil.rmtree", original_rmtree)
    assert remove_course_data(database, "Algorithms", confirmed=True) is True
    assert database.connection.execute(
        "SELECT COUNT(*) FROM pending_deletions"
    ).fetchone()[0] == 0


def test_pending_cleanup_preserves_cache_reused_by_new_course(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "state"))
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first = make_pdf_fixture(first_root / "shared.pdf")
    (second_root / "shared.pdf").write_bytes(first.read_bytes())
    database = Database()
    database.initialize()
    assert sync_course(database, "CS 101", first_root).indexed == 1
    original_rmtree = __import__("shutil").rmtree
    monkeypatch.setattr(
        "classcorpus.database.shutil.rmtree",
        lambda _: (_ for _ in ()).throw(OSError("cache is busy")),
    )
    with pytest.raises(OSError, match="cache is busy"):
        remove_course_data(database, "CS 101", confirmed=True)
    pending_path = Path(
        database.connection.execute(
            "SELECT path FROM pending_deletions"
        ).fetchone()["path"]
    )

    assert sync_course(database, "CS-101", second_root).indexed == 1
    with database.connection:
        for row in database.connection.execute(
            """
            SELECT slides.id, slides.ordinal
            FROM slides
            JOIN source_files ON source_files.id = slides.source_file_id
            JOIN courses ON courses.id = source_files.course_id
            WHERE courses.name = 'CS-101'
            """
        ).fetchall():
            database.connection.execute(
                "UPDATE slides SET render_path = ? WHERE id = ?",
                (
                    str(pending_path / f"page-{int(row['ordinal']):04d}.png"),
                    row["id"],
                ),
            )
    monkeypatch.setattr("classcorpus.database.shutil.rmtree", original_rmtree)
    cleaned = database.cleanup_pending_deletions()

    assert cleaned == 1
    assert pending_path.is_dir()
    assert database.slide_count("CS-101") == 2
    assert database.connection.execute(
        "SELECT COUNT(*) FROM pending_deletions"
    ).fetchone()[0] == 0
