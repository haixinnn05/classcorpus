from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from classcorpus.database import Database


@dataclass(frozen=True, slots=True)
class SearchResult:
    slide_id: int
    course: str
    source_file: str
    source_path: str
    ordinal: int
    kind: Literal["slide", "page"]
    title: str
    body_text: str
    speaker_notes: str
    visual_description: str | None
    render_path: str | None
    vision_status: str
    snippet: str
    score: float


def search(
    database: Database,
    query: str,
    *,
    course: str | None = None,
    limit: int = 8,
) -> list[SearchResult]:
    match_query = _fts_query(query)
    if limit < 1:
        raise ValueError("limit must be at least 1")

    parameters: list[object] = [match_query]
    course_clause = ""
    if course is not None:
        course_clause = "AND courses.name = ?"
        parameters.append(course)
    parameters.append(limit)

    rows = database.connection.execute(
        f"""
        SELECT
            slides.id AS slide_id,
            courses.name AS course,
            source_files.relative_path AS source_file,
            source_files.source_path,
            slides.ordinal,
            slides.kind,
            slides.title,
            slides.body_text,
            slides.speaker_notes,
            slides.visual_description,
            slides.render_path,
            slides.vision_status,
            snippet(slide_fts, -1, '[', ']', '...', 20) AS snippet,
            -bm25(slide_fts) AS score
        FROM slide_fts
        JOIN slides ON slides.id = CAST(slide_fts.slide_id AS INTEGER)
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE slide_fts MATCH ?
        {course_clause}
        ORDER BY bm25(slide_fts), slides.id
        LIMIT ?
        """,
        parameters,
    ).fetchall()
    return [SearchResult(**dict(row)) for row in rows]


def _fts_query(query: str) -> str:
    tokens = re.findall(r"\w+", query, flags=re.UNICODE)
    if not tokens:
        raise ValueError("query must not be blank")
    return " OR ".join(f'"{token}"' for token in tokens)


__all__ = ["SearchResult", "search"]
