import sqlite3

import pytest

from classcorpus.database import Database


def test_database_defaults_to_shared_database_path(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path))

    db = Database()

    assert db.path == tmp_path / "classcorpus.sqlite3"
    assert db.path.parent == tmp_path


def test_course_lifecycle(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    db.initialize()

    course = db.upsert_course("Algorithms", tmp_path / "lectures")
    updated = db.upsert_course("Algorithms", tmp_path / "updated-lectures")

    assert course.name == "Algorithms"
    assert course.source_root == str((tmp_path / "lectures").resolve())
    assert updated.id == course.id
    assert updated.source_root == str((tmp_path / "updated-lectures").resolve())
    assert db.connection.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 1
    assert db.remove_course("Algorithms") is True
    assert db.remove_course("Algorithms") is False


def test_schema_enables_fts(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    db.initialize()

    names = {
        row["name"]
        for row in db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
        ).fetchall()
    }

    assert "slide_fts" in names


def test_schema_enforces_required_uniqueness_and_cascade(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    db.initialize()

    course = db.upsert_course("Algorithms", tmp_path / "lectures")

    with db.connection:
        cursor = db.connection.execute(
            """
            INSERT INTO source_files(
                course_id,
                relative_path,
                source_path,
                size,
                mtime_ns,
                sha256,
                parser_version,
                status,
                error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                course.id,
                "week-1/lecture-1.pdf",
                str((tmp_path / "lectures" / "week-1" / "lecture-1.pdf").resolve()),
                123,
                456,
                "abc",
                "1",
                "ready",
                None,
            ),
        )
        source_file_id = cursor.lastrowid
        db.connection.execute(
            """
            INSERT INTO slides(
                source_file_id,
                ordinal,
                kind,
                title,
                body_text,
                speaker_notes,
                visual_description,
                render_path,
                vision_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_file_id,
                1,
                "page",
                "Shortest Paths",
                "Bellman-Ford handles negative edges.",
                "",
                None,
                None,
                "pending",
            ),
        )

    with pytest.raises(sqlite3.IntegrityError):
        with db.connection:
            db.connection.execute(
                """
                INSERT INTO source_files(
                    course_id,
                    relative_path,
                    source_path,
                    size,
                    mtime_ns,
                    sha256,
                    parser_version,
                    status,
                    error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    course.id,
                    "week-1/lecture-1.pdf",
                    str((tmp_path / "lectures" / "week-1" / "lecture-1.pdf").resolve()),
                    123,
                    456,
                    "abc",
                    "1",
                    "ready",
                    None,
                ),
            )

    with pytest.raises(sqlite3.IntegrityError):
        with db.connection:
            db.connection.execute(
                """
                INSERT INTO slides(
                    source_file_id,
                    ordinal,
                    kind,
                    title,
                    body_text,
                    speaker_notes,
                    visual_description,
                    render_path,
                    vision_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_file_id,
                    1,
                    "page",
                    "Duplicate Slide",
                    "This should fail.",
                    "",
                    None,
                    None,
                    "pending",
                ),
            )

    assert db.remove_course("Algorithms") is True
    assert (
        db.connection.execute("SELECT COUNT(*) FROM source_files").fetchone()[0] == 0
    )
    assert db.connection.execute("SELECT COUNT(*) FROM slides").fetchone()[0] == 0
