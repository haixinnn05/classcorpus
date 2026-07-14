import sqlite3
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from classcorpus.models import SlideRecord, SourceFingerprint
from classcorpus.paths import data_root, database_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    source_root TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_files (
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

CREATE TABLE IF NOT EXISTS slides (
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

CREATE VIRTUAL TABLE IF NOT EXISTS slide_fts USING fts5(
    slide_id UNINDEXED,
    title,
    body_text,
    speaker_notes,
    visual_description
);

CREATE TABLE IF NOT EXISTS slide_embeddings (
    slide_id INTEGER NOT NULL REFERENCES slides(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    dimension INTEGER NOT NULL CHECK(dimension >= 1),
    vector BLOB NOT NULL,
    PRIMARY KEY(slide_id, model_name)
);
"""


@dataclass(frozen=True, slots=True)
class Course:
    id: int
    name: str
    source_root: str


class Database:
    def __init__(self, path: Path | None = None):
        self.path = (path or database_path()).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    def initialize(self) -> None:
        with self.connection:
            self.connection.executescript(SCHEMA)

    def upsert_course(self, name: str, source_root: Path) -> Course:
        root = str(source_root.expanduser().resolve())
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO courses(name, source_root)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE
                SET source_root = excluded.source_root
                """,
                (name, root),
            )
        row = self.connection.execute(
            "SELECT id, name, source_root FROM courses WHERE name = ?",
            (name,),
        ).fetchone()
        assert row is not None
        return Course(**dict(row))

    def remove_course(self, name: str) -> bool:
        with self.connection:
            self.connection.execute(
                """
                DELETE FROM slide_fts
                WHERE slide_id IN (
                    SELECT slides.id
                    FROM slides
                    JOIN source_files ON source_files.id = slides.source_file_id
                    JOIN courses ON courses.id = source_files.course_id
                    WHERE courses.name = ?
                )
                """,
                (name,),
            )
            cursor = self.connection.execute(
                "DELETE FROM courses WHERE name = ?",
                (name,),
            )
        return cursor.rowcount > 0

    def source_is_current(
        self,
        course_id: int,
        relative_path: str,
        fingerprint: SourceFingerprint,
    ) -> bool:
        row = self.connection.execute(
            """
            SELECT sha256, parser_version, status
            FROM source_files
            WHERE course_id = ? AND relative_path = ?
            """,
            (course_id, relative_path),
        ).fetchone()
        return bool(
            row
            and row["status"] == "ready"
            and row["sha256"] == fingerprint.sha256
            and row["parser_version"] == fingerprint.parser_version
        )

    def replace_source(
        self,
        course_id: int,
        relative_path: str,
        source_path: Path,
        fingerprint: SourceFingerprint,
        slides: Sequence[SlideRecord],
    ) -> None:
        with self.connection:
            source_row = self.connection.execute(
                """
                SELECT id FROM source_files
                WHERE course_id = ? AND relative_path = ?
                """,
                (course_id, relative_path),
            ).fetchone()
            if source_row is not None:
                self.connection.execute(
                    """
                    DELETE FROM slide_fts
                    WHERE slide_id IN (
                        SELECT id FROM slides WHERE source_file_id = ?
                    )
                    """,
                    (source_row["id"],),
                )
                self.connection.execute(
                    "DELETE FROM slides WHERE source_file_id = ?",
                    (source_row["id"],),
                )

            self.connection.execute(
                """
                INSERT INTO source_files(
                    course_id, relative_path, source_path, size, mtime_ns,
                    sha256, parser_version, status, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'ready', NULL)
                ON CONFLICT(course_id, relative_path) DO UPDATE SET
                    source_path = excluded.source_path,
                    size = excluded.size,
                    mtime_ns = excluded.mtime_ns,
                    sha256 = excluded.sha256,
                    parser_version = excluded.parser_version,
                    status = 'ready',
                    error_message = NULL
                """,
                (
                    course_id,
                    relative_path,
                    str(source_path.resolve()),
                    fingerprint.size,
                    fingerprint.mtime_ns,
                    fingerprint.sha256,
                    fingerprint.parser_version,
                ),
            )
            source_id = self.connection.execute(
                """
                SELECT id FROM source_files
                WHERE course_id = ? AND relative_path = ?
                """,
                (course_id, relative_path),
            ).fetchone()["id"]

            for slide in slides:
                cursor = self.connection.execute(
                    """
                    INSERT INTO slides(
                        source_file_id, ordinal, kind, title, body_text,
                        speaker_notes, visual_description, render_path,
                        vision_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        slide.ordinal,
                        slide.kind,
                        slide.title,
                        slide.body_text,
                        slide.speaker_notes,
                        slide.visual_description,
                        slide.render_path,
                        "complete" if slide.visual_description else "pending",
                    ),
                )
                slide_id = cursor.lastrowid
                self.connection.execute(
                    """
                    INSERT INTO slide_fts(
                        slide_id, title, body_text, speaker_notes,
                        visual_description
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        slide_id,
                        slide.title,
                        slide.body_text,
                        slide.speaker_notes,
                        slide.visual_description or "",
                    ),
                )

    def record_source_error(
        self,
        course_id: int,
        relative_path: str,
        source_path: Path,
        fingerprint: SourceFingerprint,
        message: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO source_files(
                    course_id, relative_path, source_path, size, mtime_ns,
                    sha256, parser_version, status, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'failed', ?)
                ON CONFLICT(course_id, relative_path) DO UPDATE SET
                    source_path = excluded.source_path,
                    size = excluded.size,
                    mtime_ns = excluded.mtime_ns,
                    sha256 = excluded.sha256,
                    parser_version = excluded.parser_version,
                    status = 'failed',
                    error_message = excluded.error_message
                """,
                (
                    course_id,
                    relative_path,
                    str(source_path.resolve()),
                    fingerprint.size,
                    fingerprint.mtime_ns,
                    fingerprint.sha256,
                    fingerprint.parser_version,
                    message,
                ),
            )

    def slide_count(self, course_name: str) -> int:
        row = self.connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM slides
            JOIN source_files ON source_files.id = slides.source_file_id
            JOIN courses ON courses.id = source_files.course_id
            WHERE courses.name = ?
            """,
            (course_name,),
        ).fetchone()
        return int(row["count"])


def remove_course_data(
    database: Database,
    course_name: str,
    *,
    confirmed: bool,
) -> bool:
    if not confirmed:
        return False

    rows = database.connection.execute(
        """
        SELECT slides.render_path
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE courses.name = ? AND slides.render_path IS NOT NULL
        """,
        (course_name,),
    ).fetchall()
    render_root = (data_root() / "renders").resolve()
    render_directories: set[Path] = set()
    for row in rows:
        render_path = Path(row["render_path"]).expanduser().resolve()
        if not render_path.is_relative_to(render_root):
            raise ValueError(
                f"refusing to delete generated path outside ClassCorpus data directory: "
                f"{render_path}"
            )
        render_directories.add(render_path.parent)

    for directory in sorted(render_directories, key=lambda path: len(path.parts), reverse=True):
        if directory.exists():
            shutil.rmtree(directory)
    return database.remove_course(course_name)
