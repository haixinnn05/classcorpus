import json
import sqlite3

import pytest

from classcorpus.database import Database
from classcorpus.models import SlideRecord, SourceFingerprint, VisualAsset


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


def test_replace_source_preserves_lossless_extraction_fields(tmp_path):
    raw = "Title\n\n  indented detail\n" + ("x" * 120_000) + "\n"
    asset_path = tmp_path / "data" / "renders" / "course" / "asset.png"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"exact-image")
    db = Database(tmp_path / "db.sqlite3")
    db.initialize()
    course = db.upsert_course("Algorithms", tmp_path / "lectures")
    record = SlideRecord(
        ordinal=1,
        kind="page",
        title="Title",
        body_text="indented detail",
        speaker_notes="",
        raw_text=raw,
        extraction_status="review-needed",
        extraction_reasons=("embedded-image",),
        native_text_chars=len(raw),
        has_visual_content=True,
        visual_assets=(
            VisualAsset(
                path=str(asset_path),
                kind="image",
                shape_name="Picture 1",
                content_type="image/png",
                left=1,
                top=2,
                width=3,
                height=4,
            ),
        ),
    )

    db.replace_source(
        course.id,
        "lecture.pdf",
        tmp_path / "lectures" / "lecture.pdf",
        SourceFingerprint(1, 1, "abc", "2"),
        [record],
    )

    row = db.connection.execute("SELECT * FROM slides").fetchone()
    assert row is not None
    assert row["raw_text"] == raw
    assert json.loads(row["extraction_reasons"]) == ["embedded-image"]
    assert row["native_text_chars"] == len(raw)
    assert row["has_visual_content"] == 1
    asset = db.connection.execute("SELECT * FROM visual_assets").fetchone()
    assert asset is not None
    assert asset["path"] == str(asset_path)
    assert asset["shape_name"] == "Picture 1"
    assert (asset["left"], asset["top"], asset["width"], asset["height"]) == (
        1,
        2,
        3,
        4,
    )


def test_initialize_migrates_legacy_slides_for_review(tmp_path):
    db = Database(tmp_path / "db.sqlite3")

    with db.connection:
        db.connection.executescript(
            """
            CREATE TABLE courses (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                source_root TEXT NOT NULL
            );

            CREATE TABLE source_files (
                id INTEGER PRIMARY KEY,
                course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                relative_path TEXT NOT NULL,
                source_path TEXT NOT NULL,
                size INTEGER NOT NULL,
                mtime_ns INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                parser_version TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                UNIQUE(course_id, relative_path)
            );

            CREATE TABLE slides (
                id INTEGER PRIMARY KEY,
                source_file_id INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
                ordinal INTEGER NOT NULL CHECK(ordinal >= 1),
                kind TEXT NOT NULL CHECK(kind IN ('slide', 'page')),
                title TEXT NOT NULL,
                body_text TEXT NOT NULL,
                speaker_notes TEXT NOT NULL,
                visual_description TEXT,
                render_path TEXT,
                vision_status TEXT NOT NULL DEFAULT 'pending',
                UNIQUE(source_file_id, ordinal)
            );
            """
        )
        db.connection.execute(
            """
            INSERT INTO courses(id, name, source_root)
            VALUES (1, 'Algorithms', ?)
            """,
            (str((tmp_path / "lectures").resolve()),),
        )
        db.connection.execute(
            """
            INSERT INTO source_files(
                id,
                course_id,
                relative_path,
                source_path,
                size,
                mtime_ns,
                sha256,
                parser_version,
                status,
                error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                1,
                "lecture.pdf",
                str((tmp_path / "lectures" / "lecture.pdf").resolve()),
                123,
                456,
                "abc",
                "1",
                "ready",
                None,
            ),
        )
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
                1,
                1,
                "page",
                "Legacy title",
                "Legacy body",
                "",
                None,
                None,
                "pending",
            ),
        )

    db.initialize()

    row = db.connection.execute("SELECT * FROM slides").fetchone()
    assert row is not None
    assert row["raw_text"] == "Legacy title\nLegacy body"
    assert row["extraction_status"] == "review-needed"
    assert json.loads(row["extraction_reasons"]) == ["legacy-record-not-audited"]
    assert row["native_text_chars"] == len(row["raw_text"])


def test_initialize_preserves_evidence_during_partial_migration(tmp_path):
    raw = "Title\n\n  exact raw body"
    db = Database(tmp_path / "db.sqlite3")

    with db.connection:
        db.connection.executescript(
            """
            CREATE TABLE slides (
                id INTEGER PRIMARY KEY,
                source_file_id INTEGER NOT NULL,
                ordinal INTEGER NOT NULL CHECK(ordinal >= 1),
                kind TEXT NOT NULL CHECK(kind IN ('slide', 'page')),
                title TEXT NOT NULL,
                body_text TEXT NOT NULL,
                speaker_notes TEXT NOT NULL,
                raw_text TEXT NOT NULL DEFAULT '',
                extraction_status TEXT NOT NULL DEFAULT 'review-needed',
                extraction_reasons TEXT NOT NULL DEFAULT '[]',
                visual_description TEXT,
                render_path TEXT,
                vision_status TEXT NOT NULL DEFAULT 'pending',
                UNIQUE(source_file_id, ordinal)
            );
            """
        )
        db.connection.execute(
            """
            INSERT INTO slides(
                source_file_id,
                ordinal,
                kind,
                title,
                body_text,
                speaker_notes,
                raw_text,
                extraction_status,
                extraction_reasons,
                visual_description,
                render_path,
                vision_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                1,
                "page",
                "Title",
                "normalized body",
                "",
                raw,
                "text-extracted",
                '["native-text"]',
                None,
                None,
                "pending",
            ),
        )

    db.initialize()

    row = db.connection.execute("SELECT * FROM slides").fetchone()
    assert row is not None
    assert row["raw_text"] == raw
    assert row["extraction_status"] == "text-extracted"
    assert json.loads(row["extraction_reasons"]) == ["native-text"]
    assert row["native_text_chars"] == len(raw)
    assert row["has_visual_content"] == 0


def test_remove_course_cleans_up_relational_and_fts_rows(tmp_path):
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
        slide_id = db.connection.execute(
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
        ).lastrowid
        db.connection.execute(
            """
            INSERT INTO slide_fts(
                slide_id,
                title,
                body_text,
                speaker_notes,
                visual_description
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                slide_id,
                "Shortest Paths",
                "Bellman-Ford handles negative edges.",
                "",
                None,
            ),
        )

    assert db.connection.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM source_files").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM slides").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM slide_fts").fetchone()[0] == 1

    assert db.remove_course("Algorithms") is True

    assert db.connection.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM source_files").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM slides").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM slide_fts").fetchone()[0] == 0


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


@pytest.mark.parametrize("ordinal", [0, -1])
def test_schema_rejects_non_positive_ordinals(tmp_path, ordinal):
    db = Database(tmp_path / "db.sqlite3")
    db.initialize()

    course = db.upsert_course("Algorithms", tmp_path / "lectures")

    with db.connection:
        source_file_id = db.connection.execute(
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
        ).lastrowid

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
                    ordinal,
                    "page",
                    "Shortest Paths",
                    "Bellman-Ford handles negative edges.",
                    "",
                    None,
                    None,
                    "pending",
                ),
            )
