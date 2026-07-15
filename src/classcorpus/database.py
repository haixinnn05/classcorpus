import json
import sqlite3
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from classcorpus.models import SlideRecord, SourceFingerprint, VisualAsset
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
    raw_text TEXT NOT NULL DEFAULT '',
    extraction_status TEXT NOT NULL DEFAULT 'review-needed'
        CHECK(extraction_status IN (
            'text-extracted', 'review-needed', 'visually-reviewed'
        )),
    extraction_reasons TEXT NOT NULL DEFAULT '[]',
    native_text_chars INTEGER NOT NULL DEFAULT 0 CHECK(native_text_chars >= 0),
    has_visual_content INTEGER NOT NULL DEFAULT 0
        CHECK(has_visual_content IN (0, 1)),
    visual_description TEXT,
    render_path TEXT,
    vision_status TEXT NOT NULL DEFAULT 'pending',
    UNIQUE(source_file_id, ordinal)
);

CREATE TABLE IF NOT EXISTS visual_assets (
    id INTEGER PRIMARY KEY,
    slide_id INTEGER NOT NULL REFERENCES slides(id) ON DELETE CASCADE,
    asset_index INTEGER NOT NULL CHECK(asset_index >= 0),
    path TEXT NOT NULL,
    kind TEXT NOT NULL,
    shape_name TEXT NOT NULL,
    content_type TEXT NOT NULL,
    left INTEGER NOT NULL,
    top INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    UNIQUE(slide_id, asset_index)
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

CREATE TABLE IF NOT EXISTS pending_deletions (
    path TEXT PRIMARY KEY
);
"""


@dataclass(frozen=True, slots=True)
class Course:
    id: int
    name: str
    source_root: str


@dataclass(frozen=True, slots=True)
class SourceHealth:
    total: int
    ready: int
    failed: int


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
            self._migrate_slides()

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
        source_path: Path,
    ) -> bool:
        row = self.connection.execute(
            """
            SELECT sha256, parser_version, status, source_path
            FROM source_files
            WHERE course_id = ? AND relative_path = ?
            """,
            (course_id, relative_path),
        ).fetchone()
        is_current = bool(
            row
            and row["status"] == "ready"
            and row["sha256"] == fingerprint.sha256
            and row["parser_version"] == fingerprint.parser_version
        )
        resolved_source = str(source_path.expanduser().resolve())
        if is_current and row["source_path"] != resolved_source:
            with self.connection:
                self.connection.execute(
                    """
                    UPDATE source_files SET source_path = ?
                    WHERE course_id = ? AND relative_path = ?
                    """,
                    (resolved_source, course_id, relative_path),
                )
        return is_current

    def replace_source(
        self,
        course_id: int,
        relative_path: str,
        source_path: Path,
        fingerprint: SourceFingerprint,
        slides: Sequence[SlideRecord],
    ) -> tuple[dict[str, str], ...]:
        old_render_directories: set[Path] = set()
        with self.connection:
            source_row = self.connection.execute(
                """
                SELECT id FROM source_files
                WHERE course_id = ? AND relative_path = ?
                """,
                (course_id, relative_path),
            ).fetchone()
            if source_row is not None:
                old_render_directories = self._source_render_directories(
                    int(source_row["id"])
                )
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
                reasons_json = json.dumps(
                    slide.extraction_reasons,
                    ensure_ascii=True,
                    separators=(",", ":"),
                )
                cursor = self.connection.execute(
                    """
                    INSERT INTO slides(
                        source_file_id, ordinal, kind, title, body_text,
                        speaker_notes, raw_text, extraction_status,
                        extraction_reasons, native_text_chars,
                        has_visual_content, visual_description,
                        render_path, vision_status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        slide.ordinal,
                        slide.kind,
                        slide.title,
                        slide.body_text,
                        slide.speaker_notes,
                        slide.raw_text,
                        slide.extraction_status,
                        reasons_json,
                        slide.native_text_chars,
                        int(slide.has_visual_content),
                        slide.visual_description,
                        slide.render_path,
                        "complete" if slide.visual_description else "pending",
                    ),
                )
                slide_id = cursor.lastrowid
                for asset_index, asset in enumerate(slide.visual_assets):
                    self.connection.execute(
                        """
                        INSERT INTO visual_assets(
                            slide_id, asset_index, path, kind, shape_name,
                            content_type, left, top, width, height
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            slide_id,
                            asset_index,
                            asset.path,
                            asset.kind,
                            asset.shape_name,
                            asset.content_type,
                            asset.left,
                            asset.top,
                            asset.width,
                            asset.height,
                        ),
                    )
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
        return self.cleanup_render_directories(old_render_directories)

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

    def mark_source_error(
        self,
        course_id: int,
        relative_path: str,
        source_path: Path,
        parser_version: str,
        message: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO source_files(
                    course_id, relative_path, source_path, size, mtime_ns,
                    sha256, parser_version, status, error_message
                )
                VALUES (?, ?, ?, 0, 0, '', ?, 'failed', ?)
                ON CONFLICT(course_id, relative_path) DO UPDATE SET
                    source_path = excluded.source_path,
                    status = 'failed',
                    error_message = excluded.error_message
                """,
                (
                    course_id,
                    relative_path,
                    str(source_path.expanduser().resolve()),
                    parser_version,
                    message,
                ),
            )

    def remove_missing_sources(
        self,
        course_id: int,
        present_relative_paths: set[str],
    ) -> tuple[int, tuple[dict[str, str], ...]]:
        parameters: list[object] = [course_id]
        present_clause = ""
        if present_relative_paths:
            placeholders = ",".join("?" for _ in present_relative_paths)
            present_clause = f"AND relative_path NOT IN ({placeholders})"
            parameters.extend(sorted(present_relative_paths))
        rows = self.connection.execute(
            f"""
            SELECT id FROM source_files
            WHERE course_id = ? {present_clause}
            """,
            parameters,
        ).fetchall()
        source_ids = [int(row["id"]) for row in rows]
        if not source_ids:
            return 0, ()
        render_directories: set[Path] = set()
        for source_id in source_ids:
            render_directories.update(self._source_render_directories(source_id))
        placeholders = ",".join("?" for _ in source_ids)
        with self.connection:
            self.connection.execute(
                f"""
                DELETE FROM slide_fts
                WHERE slide_id IN (
                    SELECT id FROM slides
                    WHERE source_file_id IN ({placeholders})
                )
                """,
                source_ids,
            )
            self.connection.execute(
                f"DELETE FROM source_files WHERE id IN ({placeholders})",
                source_ids,
            )
        cleanup_warnings = self.cleanup_render_directories(render_directories)
        return len(source_ids), cleanup_warnings

    def cleanup_render_directories(
        self,
        directories: set[Path],
    ) -> tuple[dict[str, str], ...]:
        if not directories:
            return ()
        warnings: list[dict[str, str]] = []
        try:
            render_rows = self.connection.execute(
                "SELECT render_path FROM slides WHERE render_path IS NOT NULL"
            ).fetchall()
            referenced = {
                Path(row["render_path"]).expanduser().resolve().parent
                for row in render_rows
            }
            asset_rows = self.connection.execute(
                "SELECT path FROM visual_assets"
            ).fetchall()
            referenced.update(
                _asset_generation_directory(Path(row["path"]))
                for row in asset_rows
            )
        except (OSError, TypeError, ValueError, sqlite3.Error) as error:
            return (
                {
                    "path": str(data_root() / "renders"),
                    "type": "cache_cleanup_failed",
                    "message": str(error),
                },
            )
        for directory in sorted(
            directories,
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            try:
                resolved = _validated_render_directory(directory)
                if resolved not in referenced and resolved.exists():
                    shutil.rmtree(resolved)
            except (OSError, ValueError) as error:
                warnings.append(
                    {
                        "path": str(directory),
                        "type": "cache_cleanup_failed",
                        "message": str(error),
                    }
                )
        return tuple(warnings)

    def schedule_course_removal(
        self,
        name: str,
        render_directories: set[Path],
    ) -> bool:
        with self.connection:
            for directory in render_directories:
                self.connection.execute(
                    "INSERT OR IGNORE INTO pending_deletions(path) VALUES (?)",
                    (str(_validated_render_directory(directory)),),
                )
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

    def cleanup_pending_deletions(self) -> int:
        rows = self.connection.execute(
            "SELECT path FROM pending_deletions ORDER BY path"
        ).fetchall()
        referenced = {
            Path(row["render_path"]).expanduser().resolve().parent
            for row in self.connection.execute(
                "SELECT render_path FROM slides WHERE render_path IS NOT NULL"
            )
        }
        referenced.update(
            _asset_generation_directory(Path(row["path"]))
            for row in self.connection.execute("SELECT path FROM visual_assets")
        )
        cleaned = 0
        for row in rows:
            directory = _validated_render_directory(Path(row["path"]))
            if directory not in referenced and directory.exists():
                shutil.rmtree(directory)
            with self.connection:
                self.connection.execute(
                    "DELETE FROM pending_deletions WHERE path = ?",
                    (row["path"],),
                )
            cleaned += 1
        return cleaned

    def _source_render_directories(self, source_file_id: int) -> set[Path]:
        directories = {
            Path(row["render_path"]).expanduser().resolve().parent
            for row in self.connection.execute(
                """
                SELECT render_path FROM slides
                WHERE source_file_id = ? AND render_path IS NOT NULL
                """,
                (source_file_id,),
            )
        }
        directories.update(
            _asset_generation_directory(Path(row["path"]))
            for row in self.connection.execute(
                """
                SELECT visual_assets.path
                FROM visual_assets
                JOIN slides ON slides.id = visual_assets.slide_id
                WHERE slides.source_file_id = ?
                """,
                (source_file_id,),
            )
        )
        return directories

    def visual_assets_for_slide(self, slide_id: int) -> tuple[VisualAsset, ...]:
        rows = self.connection.execute(
            """
            SELECT path, kind, shape_name, content_type,
                   left, top, width, height
            FROM visual_assets
            WHERE slide_id = ?
            ORDER BY asset_index
            """,
            (slide_id,),
        ).fetchall()
        return tuple(VisualAsset(**dict(row)) for row in rows)

    def _migrate_slides(self) -> None:
        columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(slides)")
        }
        additions = {
            "raw_text": "TEXT NOT NULL DEFAULT ''",
            "extraction_status": "TEXT NOT NULL DEFAULT 'review-needed'",
            "extraction_reasons": (
                "TEXT NOT NULL DEFAULT '[\"legacy-record-not-audited\"]'"
            ),
            "native_text_chars": "INTEGER NOT NULL DEFAULT 0",
            "has_visual_content": "INTEGER NOT NULL DEFAULT 0",
        }
        added_columns: set[str] = set()
        for name, declaration in additions.items():
            if name not in columns:
                self.connection.execute(
                    f"ALTER TABLE slides ADD COLUMN {name} {declaration}"
                )
                added_columns.add(name)
        if "raw_text" in added_columns:
            self.connection.execute(
                """
                UPDATE slides
                SET raw_text = CASE
                        WHEN body_text = '' THEN title
                        WHEN title = '' THEN body_text
                        ELSE title || char(10) || body_text
                    END
                """
            )
        if "native_text_chars" in added_columns:
            self.connection.execute(
                "UPDATE slides SET native_text_chars = length(raw_text)"
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

    def source_health(self, course_name: str | None = None) -> SourceHealth:
        parameters: list[object] = []
        course_clause = ""
        if course_name is not None:
            course_clause = "WHERE courses.name = ?"
            parameters.append(course_name)
        row = self.connection.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN source_files.status = 'ready' THEN 1 ELSE 0 END)
                    AS ready,
                SUM(CASE WHEN source_files.status = 'failed' THEN 1 ELSE 0 END)
                    AS failed
            FROM source_files
            JOIN courses ON courses.id = source_files.course_id
            {course_clause}
            """,
            parameters,
        ).fetchone()
        return SourceHealth(
            total=int(row["total"] or 0),
            ready=int(row["ready"] or 0),
            failed=int(row["failed"] or 0),
        )

    def source_failures(
        self,
        course_name: str | None = None,
    ) -> tuple[dict[str, str], ...]:
        parameters: list[object] = []
        course_clause = ""
        if course_name is not None:
            course_clause = "AND courses.name = ?"
            parameters.append(course_name)
        rows = self.connection.execute(
            f"""
            SELECT
                courses.name AS course,
                source_files.relative_path AS source_file,
                source_files.source_path,
                source_files.error_message
            FROM source_files
            JOIN courses ON courses.id = source_files.course_id
            WHERE source_files.status = 'failed'
            {course_clause}
            ORDER BY courses.name, source_files.relative_path
            """,
            parameters,
        ).fetchall()
        return tuple(
            {
                "type": "source_failed",
                "course": str(row["course"]),
                "source_file": str(row["source_file"]),
                "source_path": str(row["source_path"]),
                "message": str(row["error_message"] or "source refresh failed"),
            }
            for row in rows
        )


def remove_course_data(
    database: Database,
    course_name: str,
    *,
    confirmed: bool,
) -> bool:
    if not confirmed:
        return False

    render_rows = database.connection.execute(
        """
        SELECT slides.render_path
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE courses.name = ? AND slides.render_path IS NOT NULL
        """,
        (course_name,),
    ).fetchall()
    render_directories: set[Path] = set()
    for row in render_rows:
        render_path = Path(row["render_path"]).expanduser().resolve()
        render_directories.add(_validated_render_directory(render_path.parent))
    asset_rows = database.connection.execute(
        """
        SELECT visual_assets.path
        FROM visual_assets
        JOIN slides ON slides.id = visual_assets.slide_id
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE courses.name = ?
        """,
        (course_name,),
    ).fetchall()
    render_directories.update(
        _validated_render_directory(_asset_generation_directory(Path(row["path"])))
        for row in asset_rows
    )

    other_references = {
        Path(row["render_path"]).expanduser().resolve().parent
        for row in database.connection.execute(
            """
            SELECT slides.render_path
            FROM slides
            JOIN source_files ON source_files.id = slides.source_file_id
            JOIN courses ON courses.id = source_files.course_id
            WHERE courses.name != ? AND slides.render_path IS NOT NULL
            """,
            (course_name,),
        )
    }
    other_references.update(
        _asset_generation_directory(Path(row["path"]))
        for row in database.connection.execute(
            """
            SELECT visual_assets.path
            FROM visual_assets
            JOIN slides ON slides.id = visual_assets.slide_id
            JOIN source_files ON source_files.id = slides.source_file_id
            JOIN courses ON courses.id = source_files.course_id
            WHERE courses.name != ?
            """,
            (course_name,),
        )
    )
    removed = database.schedule_course_removal(
        course_name,
        render_directories - other_references,
    )
    cleaned = database.cleanup_pending_deletions()
    return removed or cleaned > 0


def _validated_render_directory(directory: Path) -> Path:
    render_root = (data_root() / "renders").resolve()
    resolved = directory.expanduser().resolve()
    if resolved == render_root or not resolved.is_relative_to(render_root):
        raise ValueError(
            "refusing to delete generated path outside ClassCorpus data directory: "
            f"{resolved}"
        )
    return resolved


def _asset_generation_directory(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    return resolved.parent.parent
