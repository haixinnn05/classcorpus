from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from classcorpus.citations import format_citation
from classcorpus.database import Database
from classcorpus.payloads import with_estimated_tokens
from classcorpus.record_text import (
    MAX_CHUNK_CHARS,
    RECORD_TEXT_FIELDS,
    RecordTextField,
    read_record_text,
)
from classcorpus.search import SearchResult, search, suggest_terms
from classcorpus.security import mark_untrusted_content

DEFAULT_FOCUSED_LIMIT = 3
DEFAULT_FOCUSED_READ_CHARS = 900


def retrieve_focused(
    database: Database,
    query: str,
    *,
    course: str,
    source_file: str | None = None,
    ordinal: int | None = None,
    limit: int = DEFAULT_FOCUSED_LIMIT,
    field: RecordTextField = "searchable",
    read_limit: int = DEFAULT_FOCUSED_READ_CHARS,
) -> dict[str, Any]:
    if field not in RECORD_TEXT_FIELDS:
        raise ValueError(
            "field must be one of: " + ", ".join(RECORD_TEXT_FIELDS)
        )
    if read_limit < 1 or read_limit > MAX_CHUNK_CHARS:
        raise ValueError(
            f"read_limit must be between 1 and {MAX_CHUNK_CHARS}"
        )

    results = search(
        database,
        query,
        course=course,
        source_file=source_file,
        ordinal=ordinal,
        limit=limit,
    )
    health = database.source_health(course)
    warnings = list(database.source_failures(course))
    warnings.extend(
        {
            "type": "extraction_review_needed",
            "course": result.course,
            "source_file": result.source_file,
            "ordinal": str(result.ordinal),
            "reasons": list(result.extraction_reasons),
            "message": "Returned evidence may have incomplete native extraction.",
        }
        for result in results
        if result.extraction_status == "review-needed"
    )
    payload: dict[str, Any] = {
        "ok": True,
        "course": course,
        "selected": None,
        "alternatives": [],
        "sync_required": health.total == 0 or health.failed > 0,
        "warnings": warnings,
        "suggested_terms": [] if results else suggest_terms(database, query),
    }
    mark_untrusted_content(payload)
    message = _message(results, total=health.total, failed=health.failed)
    if message is not None:
        payload["message"] = message

    if results:
        selected = results[0]
        passage_offset = _passage_offset(
            _record_text(selected, field),
            query,
            read_limit,
        )
        chunk = read_record_text(
            database,
            course=selected.course,
            source_file=selected.source_file,
            ordinal=selected.ordinal,
            field=field,
            offset=passage_offset,
            limit=read_limit,
        )
        payload["selected"] = {
            **_candidate(selected, rank=1),
            "field": chunk.field,
            "text": chunk.text,
            "offset": chunk.offset,
            "total_chars": chunk.total_chars,
            "returned_chars": chunk.returned_chars,
            "has_previous": chunk.offset > 0,
            "previous_offset": max(0, chunk.offset - read_limit)
            if chunk.offset > 0
            else None,
            "has_more": chunk.has_more,
            "next_offset": chunk.next_offset,
        }
        payload["alternatives"] = [
            _candidate(result, rank=rank)
            for rank, result in enumerate(results[1:], start=2)
        ]

    payload["cache_key"] = _cache_key(payload)
    return with_estimated_tokens(payload)


def _record_text(
    result: SearchResult,
    field: RecordTextField,
) -> str:
    if field != "searchable":
        value = getattr(result, field)
        return str(value or "")
    parts = [
        ("Title", result.title),
        ("Body", result.body_text),
        ("Speaker notes", result.speaker_notes),
        ("Visual description", result.visual_description),
        ("OCR", result.ocr_text),
    ]
    return "\n\n".join(
        f"{label}:\n{value}" for label, value in parts if value
    )


def _passage_offset(text: str, query: str, limit: int) -> int:
    if len(text) <= limit:
        return 0
    terms = list(
        dict.fromkeys(re.findall(r"\w+", query.casefold(), flags=re.UNICODE))
    )
    if not terms:
        return 0
    anchors = [
        match.start()
        for term in terms
        for match in re.finditer(re.escape(term), text, flags=re.IGNORECASE)
    ]
    if not anchors:
        return 0

    phrase = " ".join(terms)
    best_start = 0
    best_score: tuple[int, int, int, int] | None = None
    for anchor in anchors:
        start = max(0, min(anchor - limit // 3, len(text) - limit))
        boundary = text.rfind("\n\n", max(0, start - 160), start)
        if boundary >= 0:
            start = boundary + 2
        segment = text[start : start + limit].casefold()
        matched = sum(term in segment for term in terms)
        occurrences = sum(segment.count(term) for term in terms)
        score = (
            matched,
            int(phrase in " ".join(re.findall(r"\w+", segment))),
            occurrences,
            -start,
        )
        if best_score is None or score > best_score:
            best_start = start
            best_score = score
    return best_start


def _candidate(result: SearchResult, *, rank: int) -> dict[str, object]:
    candidate: dict[str, object] = {
        "rank": rank,
        "source_file": result.source_file,
        "ordinal": result.ordinal,
        "kind": result.kind,
        "title": result.title,
        "source_status": result.source_status,
        "extraction_status": result.extraction_status,
        "extraction_reasons": result.extraction_reasons,
        "score": result.score,
        "lexical_coverage": result.lexical_coverage,
        "lexical_title_matches": result.lexical_title_matches,
        "lexical_phrase_match": result.lexical_phrase_match,
        "citation": format_citation(result),
    }
    if result.source_error is not None:
        candidate["source_error"] = result.source_error
    return candidate


def _cache_key(payload: dict[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _message(
    results: list[SearchResult],
    *,
    total: int,
    failed: int,
) -> str | None:
    if not results:
        if total == 0:
            return (
                "No indexed course evidence is available. Synchronize the "
                "course with index_lectures.py."
            )
        if failed:
            return (
                "No evidence matched and one or more sources failed their "
                "latest refresh. Synchronize the course and inspect warnings."
            )
        return (
            "No indexed evidence matched. Search with alternative terms or "
            "adjust the source and ordinal filters."
        )
    if failed and any(result.source_status == "failed" for result in results):
        return (
            "Some returned results come from sources whose latest refresh "
            "failed. Synchronize the course and inspect warnings before "
            "relying on them."
        )
    if failed:
        return (
            "Other indexed sources failed their latest refresh; returned "
            "results are from ready sources. Synchronize the course and "
            "inspect warnings for missing coverage."
        )
    return None


__all__ = [
    "DEFAULT_FOCUSED_LIMIT",
    "DEFAULT_FOCUSED_READ_CHARS",
    "retrieve_focused",
]
