from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Literal

from classcorpus.database import Database
from classcorpus.models import ExtractionStatus, VisualAsset


@dataclass(frozen=True, slots=True)
class LectureRecord:
    slide_id: int
    course: str
    source_file: str
    source_path: str
    source_status: str
    source_error: str | None
    ordinal: int
    kind: Literal["slide", "page"]
    title: str
    body_text: str
    speaker_notes: str
    raw_text: str
    extraction_status: ExtractionStatus
    extraction_reasons: tuple[str, ...]
    native_text_chars: int
    has_visual_content: bool
    visual_description: str | None
    render_path: str | None
    vision_status: str
    ocr_text: str | None
    ocr_confidence: float | None
    ocr_backend: str | None
    ocr_status: str
    visual_assets: tuple[VisualAsset, ...]
    citation: str


@dataclass(frozen=True, slots=True)
class RecordPage:
    records: tuple[LectureRecord, ...]
    total_records: int
    returned_records: int
    has_more: bool
    next_cursor: str | None
    review_needed: int
    warnings: tuple[dict[str, object], ...]


def read_records(
    database: Database,
    *,
    course: str,
    source_file: str | None = None,
    ordinal: int | None = None,
    cursor: str | None = None,
    limit: int = 20,
) -> RecordPage:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if ordinal is not None and ordinal < 1:
        raise ValueError("ordinal must be at least 1")
    if ordinal is not None and cursor is not None:
        raise ValueError("cursor cannot be used with ordinal")
    continuation = _decode_cursor(cursor) if cursor is not None else None
    scope_clause, scope_parameters = _scope(course, source_file, ordinal)

    summary = database.connection.execute(
        f"""
        SELECT
            COUNT(*) AS total_records,
            COALESCE(SUM(slides.extraction_status = 'review-needed'), 0)
                AS review_needed
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE {scope_clause}
        """,
        scope_parameters,
    ).fetchone()

    page_clause = ""
    parameters = list(scope_parameters)
    if continuation is not None:
        page_clause = """
            AND (
                source_files.relative_path > ?
                OR (
                    source_files.relative_path = ?
                    AND slides.ordinal > ?
                )
            )
        """
        parameters.extend(
            [
                continuation[0],
                continuation[0],
                continuation[1],
            ]
        )
    parameters.append(limit + 1)
    rows = database.connection.execute(
        f"""
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
            slides.extraction_status,
            slides.extraction_reasons,
            slides.native_text_chars,
            slides.has_visual_content,
            slides.visual_description,
            slides.render_path,
            slides.vision_status,
            slides.ocr_text,
            slides.ocr_confidence,
            slides.ocr_backend,
            slides.ocr_status
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE {scope_clause}
        {page_clause}
        ORDER BY source_files.relative_path, slides.ordinal
        LIMIT ?
        """,
        parameters,
    ).fetchall()
    has_more = len(rows) > limit
    visible_rows = rows[:limit]
    records = tuple(_record_from_row(database, row) for row in visible_rows)
    next_cursor = None
    if has_more and records:
        last = records[-1]
        next_cursor = _encode_cursor(last.source_file, last.ordinal)

    review_needed = int(summary["review_needed"])
    warnings: list[dict[str, object]] = list(
        database.source_failures(course)
    )
    if review_needed:
        warnings.append(
            {
                "type": "extraction_review_needed",
                "course": course,
                "source_file": source_file,
                "records": review_needed,
                "message": (
                    "The requested scope contains records that need visual review."
                ),
            }
        )
    return RecordPage(
        records=records,
        total_records=int(summary["total_records"]),
        returned_records=len(records),
        has_more=has_more,
        next_cursor=next_cursor,
        review_needed=review_needed,
        warnings=tuple(warnings),
    )


def _scope(
    course: str,
    source_file: str | None,
    ordinal: int | None,
) -> tuple[str, list[object]]:
    clauses = ["courses.name = ?"]
    parameters: list[object] = [course]
    if source_file is not None:
        clauses.append("source_files.relative_path = ?")
        parameters.append(source_file)
    if ordinal is not None:
        clauses.append("slides.ordinal = ?")
        parameters.append(ordinal)
    return " AND ".join(clauses), parameters


def _record_from_row(database: Database, row) -> LectureRecord:
    values = dict(row)
    values["extraction_reasons"] = tuple(
        json.loads(values["extraction_reasons"])
    )
    values["has_visual_content"] = bool(values["has_visual_content"])
    values["visual_assets"] = database.visual_assets_for_slide(
        int(values["slide_id"])
    )
    label = "Slide" if values["kind"] == "slide" else "Page"
    values["citation"] = (
        f"[{values['course']}, {values['source_file']}, "
        f"{label} {values['ordinal']}]"
    )
    return LectureRecord(**values)


def _encode_cursor(source_file: str, ordinal: int) -> str:
    payload = json.dumps(
        {"source_file": source_file, "ordinal": ordinal},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[str, int]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = base64.b64decode(
            cursor + padding,
            altchars=b"-_",
            validate=True,
        )
        value = json.loads(payload.decode("utf-8"))
        if (
            not isinstance(value, dict)
            or set(value) != {"source_file", "ordinal"}
            or not isinstance(value["source_file"], str)
            or not value["source_file"]
            or not isinstance(value["ordinal"], int)
            or isinstance(value["ordinal"], bool)
            or value["ordinal"] < 1
        ):
            raise ValueError
    except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("cursor is malformed") from error
    return value["source_file"], value["ordinal"]


__all__ = ["LectureRecord", "RecordPage", "read_records"]
