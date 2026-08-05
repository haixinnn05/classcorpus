from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from classcorpus.database import Database

if TYPE_CHECKING:
    from classcorpus.search import SearchResult


CITATION_PATTERN = re.compile(
    r"\[[^\]\n]+,\s*(?:(?:Slide|Page)\s+\d+|"
    r"\d{2,}:\d{2}(?::\d{2})?(?:\.\d{3})?)\]"
)


@dataclass(frozen=True, slots=True)
class CitationLocation:
    course: str
    source_file: str
    ordinal: int
    kind: str
    start_ms: int | None
    end_ms: int | None


def format_citation(result: SearchResult) -> str:
    return format_record_citation(
        course=result.course,
        source_file=result.source_file,
        kind=result.kind,
        ordinal=result.ordinal,
        start_ms=result.start_ms,
    )


def format_record_citation(
    *,
    course: str,
    source_file: str,
    kind: str,
    ordinal: int,
    start_ms: int | None = None,
) -> str:
    location = (
        format_timestamp(start_ms)
        if start_ms is not None
        else f"{'Slide' if kind == 'slide' else 'Page'} {ordinal}"
    )
    return f"[{course}, {source_file}, {location}]"


def format_timestamp(milliseconds: int) -> str:
    if milliseconds < 0:
        raise ValueError("timestamp must not be negative")
    total_seconds, remainder = divmod(milliseconds, 1000)
    hours, remainder_seconds = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder_seconds, 60)
    base = (
        f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        if hours
        else f"{minutes:02d}:{seconds:02d}"
    )
    return f"{base}.{remainder:03d}" if remainder else base


def logical_record_kind(kind: str, start_ms: int | None) -> str:
    return "transcript" if start_ms is not None else kind


def resolve_citation(
    database: Database,
    citation: str,
) -> CitationLocation | None:
    rows = database.connection.execute(
        """
        SELECT courses.name AS course,
               source_files.relative_path AS source_file,
               slides.ordinal, slides.kind, slides.start_ms, slides.end_ms
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        """
    ).fetchall()
    wanted = citation.strip()
    for row in rows:
        start_ms = int(row["start_ms"]) if row["start_ms"] is not None else None
        kind = logical_record_kind(str(row["kind"]), start_ms)
        formatted = format_record_citation(
            course=str(row["course"]),
            source_file=str(row["source_file"]),
            kind=kind,
            ordinal=int(row["ordinal"]),
            start_ms=start_ms,
        )
        if formatted != wanted:
            continue
        return CitationLocation(
            course=str(row["course"]),
            source_file=str(row["source_file"]),
            ordinal=int(row["ordinal"]),
            kind=kind,
            start_ms=start_ms,
            end_ms=(int(row["end_ms"]) if row["end_ms"] is not None else None),
        )
    return None


__all__ = [
    "CITATION_PATTERN",
    "CitationLocation",
    "format_citation",
    "format_record_citation",
    "format_timestamp",
    "logical_record_kind",
    "resolve_citation",
]
