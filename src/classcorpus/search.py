from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from typing import Literal

from classcorpus.database import Database
from classcorpus.embeddings import Encoder, semantic_ranking
from classcorpus.models import ExtractionStatus


@dataclass(frozen=True, slots=True)
class SearchResult:
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
    snippet: str
    score: float


def search(
    database: Database,
    query: str,
    *,
    course: str | None = None,
    source_file: str | None = None,
    ordinal: int | None = None,
    limit: int = 8,
    encoder: Encoder | None = None,
) -> list[SearchResult]:
    match_query = _fts_query(query)
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if ordinal is not None and ordinal < 1:
        raise ValueError("ordinal must be at least 1")

    parameters: list[object] = [match_query]
    filter_clauses: list[str] = []
    if course is not None:
        filter_clauses.append("courses.name = ?")
        parameters.append(course)
    if source_file is not None:
        filter_clauses.append("source_files.relative_path = ?")
        parameters.append(source_file)
    if ordinal is not None:
        filter_clauses.append("slides.ordinal = ?")
        parameters.append(ordinal)
    filter_sql = "".join(f" AND {clause}" for clause in filter_clauses)
    parameters.append(limit)

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
            snippet(slide_fts, -1, '[', ']', '...', 20) AS snippet,
            -bm25(slide_fts) AS score
        FROM slide_fts
        JOIN slides ON slides.id = CAST(slide_fts.slide_id AS INTEGER)
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE slide_fts MATCH ?
        {filter_sql}
        ORDER BY bm25(slide_fts), slides.id
        LIMIT ?
        """,
        parameters,
    ).fetchall()
    fts_results = [_row_to_search_result(row) for row in rows]
    if encoder is None:
        return fts_results

    semantic_ids = semantic_ranking(
        database,
        query,
        encoder,
        course=course,
        source_file=source_file,
        ordinal=ordinal,
    )
    rankings = [
        [result.slide_id for result in fts_results],
        semantic_ids,
    ]
    fused = reciprocal_rank_fusion(rankings)
    ordered_ids = sorted(fused, key=lambda slide_id: (-fused[slide_id], slide_id))[
        :limit
    ]
    by_id = {result.slide_id: result for result in fts_results}
    missing_ids = [slide_id for slide_id in ordered_ids if slide_id not in by_id]
    if missing_ids:
        by_id.update(_results_by_id(database, missing_ids))
    return [
        replace(by_id[slide_id], score=fused[slide_id])
        for slide_id in ordered_ids
        if slide_id in by_id
    ]


def _fts_query(query: str) -> str:
    tokens = re.findall(r"\w+", query, flags=re.UNICODE)
    if not tokens:
        raise ValueError("query must not be blank")
    return " OR ".join(f'"{token}"' for token in tokens)


def reciprocal_rank_fusion(
    rankings: list[list[int]],
    *,
    constant: int = 60,
) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, slide_id in enumerate(ranking, start=1):
            scores[slide_id] = scores.get(slide_id, 0.0) + 1.0 / (constant + rank)
    return scores


def _row_to_search_result(row) -> SearchResult:
    values = dict(row)
    values["extraction_reasons"] = tuple(
        json.loads(values["extraction_reasons"])
    )
    values["has_visual_content"] = bool(values["has_visual_content"])
    return SearchResult(**values)


def _results_by_id(
    database: Database,
    slide_ids: list[int],
) -> dict[int, SearchResult]:
    placeholders = ",".join("?" for _ in slide_ids)
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
            slides.title AS snippet,
            0.0 AS score
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE slides.id IN ({placeholders})
        """,
        slide_ids,
    ).fetchall()
    return {
        int(row["slide_id"]): _row_to_search_result(row)
        for row in rows
    }


__all__ = ["SearchResult", "reciprocal_rank_fusion", "search"]
