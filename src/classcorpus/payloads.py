from __future__ import annotations

from dataclasses import asdict
import json
import math
from typing import Any, Iterable

from classcorpus.citations import format_citation
from classcorpus.search import SearchResult

DEFAULT_SEARCH_BUDGET_TOKENS = 1_200
MAX_COMPACT_RESULTS = 6


def estimate_tokens(value: object) -> int:
    """Estimate model tokens from compact UTF-8 JSON at four characters each."""
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return math.ceil(len(serialized) / 4)


def search_response(
    results: Iterable[SearchResult],
    *,
    warnings: Iterable[dict[str, object]],
    sync_required: bool,
    suggested_terms: Iterable[str],
    message: str | None = None,
    full: bool = False,
    budget_tokens: int = DEFAULT_SEARCH_BUDGET_TOKENS,
    compact_option_used: bool = False,
) -> dict[str, Any]:
    if budget_tokens < 1:
        raise ValueError("budget_tokens must be at least 1")

    materialized = list(results)
    common: dict[str, Any] = {
        "ok": True,
        "sync_required": sync_required,
        "warnings": list(warnings),
        "suggested_terms": list(suggested_terms),
    }
    if compact_option_used:
        common["deprecated_options"] = ["--compact"]
    if message is not None:
        common["message"] = message

    if full:
        payload = {
            **common,
            "results": [
                {**asdict(result), "citation": format_citation(result)}
                for result in materialized
            ],
            "compact": False,
            "omitted_content_chars": 0,
            "budget_tokens": None,
            "budget_exhausted": False,
            "continuation": None,
        }
        return with_estimated_tokens(payload)

    visible = materialized[:MAX_COMPACT_RESULTS]
    sources, source_ids = _compact_sources(visible)
    payload_results = [
        compact_search_result(
            result,
            rank=rank,
            source_id=source_ids[_source_key(result)],
            evidence="",
        )
        for rank, result in enumerate(visible, start=1)
    ]
    payload = {
        **common,
        "results": payload_results,
        "sources": sources,
        "compact": True,
        "omitted_content_chars": sum(
            int(item["omitted_content_chars"]) for item in payload_results
        ),
        "budget_tokens": budget_tokens,
        "budget_exhausted": len(materialized) > len(visible),
        "continuation": {
            "type": "read_selected",
            "field": "searchable",
            "default_limit_chars": 2_000,
        }
        if visible
        else None,
    }
    _allocate_evidence(payload, visible, budget_tokens)
    return with_estimated_tokens(payload)


def compact_search_result(
    result: SearchResult,
    *,
    rank: int = 1,
    source_id: str = "s1",
    evidence: str | None = None,
) -> dict[str, object]:
    omitted_fields = (
        result.body_text,
        result.speaker_notes,
        result.raw_text,
        result.visual_description or "",
        result.ocr_text or "",
    )
    visible_evidence = result.snippet if evidence is None else evidence
    return {
        "rank": rank,
        "source_id": source_id,
        "ordinal": result.ordinal,
        "kind": result.kind,
        "title": result.title,
        "extraction_status": result.extraction_status,
        "extraction_reasons": result.extraction_reasons,
        "native_text_chars": result.native_text_chars,
        "score": result.score,
        "lexical_coverage": result.lexical_coverage,
        "lexical_title_matches": result.lexical_title_matches,
        "lexical_phrase_match": result.lexical_phrase_match,
        "citation": format_citation(result),
        "evidence": visible_evidence,
        "omitted_content_chars": (
            sum(len(value) for value in omitted_fields)
            + len(result.snippet)
            - len(visible_evidence)
        ),
    }


def with_estimated_tokens(payload: dict[str, Any]) -> dict[str, Any]:
    payload["estimated_tokens"] = 0
    while True:
        estimate = estimate_tokens(payload)
        if payload["estimated_tokens"] == estimate:
            return payload
        payload["estimated_tokens"] = estimate


def _allocate_evidence(
    payload: dict[str, Any],
    results: list[SearchResult],
    budget_tokens: int,
) -> None:
    payload_results = payload["results"]
    assert isinstance(payload_results, list)
    for item, result in zip(payload_results, results, strict=True):
        item["evidence"] = result.snippet
        item["omitted_content_chars"] = int(item["omitted_content_chars"]) - len(
            result.snippet
        )
        if estimate_tokens({**payload, "estimated_tokens": 0}) <= budget_tokens:
            continue

        item["evidence"] = ""
        item["omitted_content_chars"] = int(item["omitted_content_chars"]) + len(
            result.snippet
        )
        remaining_tokens = max(
            0,
            budget_tokens
            - estimate_tokens({**payload, "estimated_tokens": 0}),
        )
        shortened = _truncate_text(result.snippet, remaining_tokens * 4)
        item["evidence"] = shortened
        item["omitted_content_chars"] = int(item["omitted_content_chars"]) - len(
            shortened
        )
        payload["budget_exhausted"] = True

    payload["omitted_content_chars"] = sum(
        int(item["omitted_content_chars"]) for item in payload_results
    )
    if estimate_tokens({**payload, "estimated_tokens": 0}) > budget_tokens:
        payload["budget_exhausted"] = True


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit < 4:
        return ""
    prefix = text[: limit - 3].rstrip()
    if " " in prefix:
        prefix = prefix.rsplit(" ", 1)[0]
    return prefix + "..." if prefix else ""


def _compact_sources(
    results: Iterable[SearchResult],
) -> tuple[dict[str, dict[str, object]], dict[tuple[object, ...], str]]:
    sources: dict[str, dict[str, object]] = {}
    source_ids: dict[tuple[object, ...], str] = {}
    for result in results:
        key = _source_key(result)
        if key in source_ids:
            continue
        source_id = f"s{len(source_ids) + 1}"
        source_ids[key] = source_id
        source = {
            "course": result.course,
            "source_file": result.source_file,
            "source_path": result.source_path,
            "source_status": result.source_status,
            "source_error": result.source_error,
        }
        sources[source_id] = source
    return sources, source_ids


def _source_key(result: SearchResult) -> tuple[object, ...]:
    return (
        result.course,
        result.source_file,
        result.source_path,
        result.source_status,
        result.source_error,
    )


__all__ = [
    "DEFAULT_SEARCH_BUDGET_TOKENS",
    "MAX_COMPACT_RESULTS",
    "compact_search_result",
    "estimate_tokens",
    "search_response",
    "with_estimated_tokens",
]
