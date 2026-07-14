import sqlite3
from dataclasses import dataclass
from pathlib import Path

from classcorpus.paths import database_path

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
    ordinal INTEGER NOT NULL,
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
            cursor = self.connection.execute(
                "DELETE FROM courses WHERE name = ?",
                (name,),
            )
        return cursor.rowcount > 0
