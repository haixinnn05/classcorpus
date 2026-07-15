from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from difflib import get_close_matches
from typing import Literal

from classcorpus.database import Database
from classcorpus.embeddings import Encoder, semantic_ranking
from classcorpus.models import ExtractionStatus, VisualAsset

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "for",
        "from",
        "how",
        "in",
        "is",
        "of",
        "on",
        "or",
        "the",
        "to",
        "what",
        "when",
        "where",
        "why",
        "with",
    }
)


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
    ocr_text: str | None
    ocr_confidence: float | None
    ocr_backend: str | None
    ocr_status: str
    snippet: str
    score: float
    lexical_coverage: float = 0.0
    lexical_title_matches: int = 0
    lexical_phrase_match: bool = False
    visual_assets: tuple[VisualAsset, ...] = ()


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
    candidate_limit = max(limit * 4, 32)
    parameters.append(candidate_limit)

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
            slides.ocr_status,
            snippet(slide_fts, -1, '[', ']', '...', 20) AS snippet,
            -bm25(slide_fts, 0.0, 5.0, 2.0, 3.0, 2.0, 1.5) AS score
        FROM slide_fts
        JOIN slides ON slides.id = CAST(slide_fts.slide_id AS INTEGER)
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE slide_fts MATCH ?
        {filter_sql}
        ORDER BY
            bm25(slide_fts, 0.0, 5.0, 2.0, 3.0, 2.0, 1.5),
            slides.id
        LIMIT ?
        """,
        parameters,
    ).fetchall()
    fts_results = _rerank_lexical(
        [_row_to_search_result(database, row) for row in rows],
        query,
    )
    if encoder is None:
        return fts_results[:limit]

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


def suggest_terms(
    database: Database,
    query: str,
    *,
    limit: int = 5,
) -> list[str]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    tokens = _query_tokens(query)
    suggestions: list[str] = []
    for token in tokens:
        if len(token) < 4:
            continue
        rows = database.connection.execute(
            """
            SELECT term
            FROM slide_fts_vocab
            WHERE length(term) BETWEEN ? AND ?
            ORDER BY doc DESC, term
            LIMIT 2000
            """,
            (max(1, len(token) - 2), len(token) + 2),
        ).fetchall()
        candidates = [str(row["term"]) for row in rows]
        for match in get_close_matches(token, candidates, n=2, cutoff=0.72):
            if match != token and match not in suggestions:
                suggestions.append(match)
                if len(suggestions) == limit:
                    return suggestions
    return suggestions


def _rerank_lexical(
    results: list[SearchResult],
    query: str,
) -> list[SearchResult]:
    tokens = _ranking_tokens(query)
    minimum_matches = min(2, len(tokens))
    phrase = " ".join(_query_tokens(query))
    reranked: list[SearchResult] = []
    for base_rank, result in enumerate(results, start=1):
        title_tokens = set(_query_tokens(result.title))
        all_text = "\n".join(
            value
            for value in (
                result.title,
                result.body_text,
                result.speaker_notes,
                result.visual_description,
                result.ocr_text,
            )
            if value
        )
        all_tokens = set(_query_tokens(all_text))
        title_matches = sum(token in title_tokens for token in tokens)
        matched_terms = sum(token in all_tokens for token in tokens)
        if matched_terms < minimum_matches:
            continue
        coverage = matched_terms / len(tokens)
        title_coverage = title_matches / len(tokens)
        normalized_text = " ".join(_query_tokens(all_text))
        phrase_match = bool(phrase and phrase in normalized_text)
        score = (
            4.0 * coverage
            + 1.5 * title_coverage
            + 2.0 * float(phrase_match)
            + 1.0 / (60 + base_rank)
        )
        reranked.append(
            replace(
                result,
                score=score,
                lexical_coverage=coverage,
                lexical_title_matches=title_matches,
                lexical_phrase_match=phrase_match,
            )
        )
    reranked.sort(
        key=lambda result: (
            -result.score,
            result.slide_id,
        )
    )
    return reranked


def _query_tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


def _ranking_tokens(query: str) -> list[str]:
    tokens = list(dict.fromkeys(_query_tokens(query)))
    informative = [token for token in tokens if token not in _STOPWORDS]
    return informative or tokens


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


def _row_to_search_result(database: Database, row) -> SearchResult:
    values = dict(row)
    values["extraction_reasons"] = tuple(
        json.loads(values["extraction_reasons"])
    )
    values["has_visual_content"] = bool(values["has_visual_content"])
    values["visual_assets"] = database.visual_assets_for_slide(
        int(values["slide_id"])
    )
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
            slides.ocr_text,
            slides.ocr_confidence,
            slides.ocr_backend,
            slides.ocr_status,
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
        int(row["slide_id"]): _row_to_search_result(database, row)
        for row in rows
    }


__all__ = [
    "SearchResult",
    "reciprocal_rank_fusion",
    "search",
    "suggest_terms",
]
