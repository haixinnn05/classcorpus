from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Literal

from classcorpus.database import Database
from classcorpus.models import ExtractionStatus

RecordTextField = Literal[
    "searchable",
    "raw_text",
    "body_text",
    "speaker_notes",
    "visual_description",
    "ocr_text",
]
RECORD_TEXT_FIELDS = (
    "searchable",
    "raw_text",
    "body_text",
    "speaker_notes",
    "visual_description",
    "ocr_text",
)
MAX_CHUNK_CHARS = 50_000


@dataclass(frozen=True, slots=True)
class RecordTextChunk:
    slide_id: int
    course: str
    source_file: str
    source_path: str
    source_status: str
    source_error: str | None
    ordinal: int
    kind: str
    title: str
    extraction_status: ExtractionStatus
    extraction_reasons: tuple[str, ...]
    field: RecordTextField
    text: str
    total_chars: int
    offset: int
    returned_chars: int
    has_more: bool
    next_offset: int | None
    citation: str


def read_record_text(
    database: Database,
    *,
    course: str,
    source_file: str,
    ordinal: int,
    field: RecordTextField = "searchable",
    offset: int = 0,
    limit: int = 8_000,
) -> RecordTextChunk:
    if ordinal < 1:
        raise ValueError("ordinal must be at least 1")
    if field not in RECORD_TEXT_FIELDS:
        raise ValueError(
            "field must be one of: " + ", ".join(RECORD_TEXT_FIELDS)
        )
    if offset < 0:
        raise ValueError("offset must not be negative")
    if limit < 1 or limit > MAX_CHUNK_CHARS:
        raise ValueError(
            f"limit must be between 1 and {MAX_CHUNK_CHARS}"
        )
    row = database.connection.execute(
        """
        SELECT
            slides.id AS slide_id,
            courses.name AS course,
            source_files.relative_path AS source_file,
            source_files.source_path,
            source_files.status AS source_status,
            source_files.error_message AS source_error,
            slides.ordinal,
            slides.kind,
            slides.title,
            slides.body_text,
            slides.speaker_notes,
            slides.raw_text,
            slides.visual_description,
            slides.ocr_text,
            slides.extraction_status,
            slides.extraction_reasons
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE courses.name = ?
          AND source_files.relative_path = ?
          AND slides.ordinal = ?
        """,
        (course, source_file, ordinal),
    ).fetchone()
    if row is None:
        raise ValueError(
            f"record not found: {course}, {source_file}, ordinal {ordinal}"
        )
    complete_text = _selected_text(row, field)
    if offset > len(complete_text):
        raise ValueError("offset exceeds field length")
    text = complete_text[offset : offset + limit]
    next_offset = offset + len(text)
    has_more = next_offset < len(complete_text)
    label = "Slide" if row["kind"] == "slide" else "Page"
    return RecordTextChunk(
        slide_id=int(row["slide_id"]),
        course=str(row["course"]),
        source_file=str(row["source_file"]),
        source_path=str(row["source_path"]),
        source_status=str(row["source_status"]),
        source_error=(
            str(row["source_error"])
            if row["source_error"] is not None
            else None
        ),
        ordinal=int(row["ordinal"]),
        kind=str(row["kind"]),
        title=str(row["title"]),
        extraction_status=row["extraction_status"],
        extraction_reasons=tuple(json.loads(row["extraction_reasons"])),
        field=field,
        text=text,
        total_chars=len(complete_text),
        offset=offset,
        returned_chars=len(text),
        has_more=has_more,
        next_offset=next_offset if has_more else None,
        citation=(
            f"[{row['course']}, {row['source_file']}, "
            f"{label} {row['ordinal']}]"
        ),
    )


def _selected_text(row, field: RecordTextField) -> str:
    if field != "searchable":
        return str(row[field] or "")
    parts = [
        ("Title", row["title"]),
        ("Body", row["body_text"]),
        ("Speaker notes", row["speaker_notes"]),
        ("Visual description", row["visual_description"]),
        ("OCR", row["ocr_text"]),
    ]
    return "\n\n".join(
        f"{label}:\n{value}" for label, value in parts if value
    )


__all__ = [
    "MAX_CHUNK_CHARS",
    "RECORD_TEXT_FIELDS",
    "RecordTextChunk",
    "RecordTextField",
    "read_record_text",
]
