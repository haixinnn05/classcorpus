import json

from classcorpus.payloads import estimate_tokens, search_response
from classcorpus.search import SearchResult


def _result(*, slide_id: int = 1, raw_text: str = "evidence") -> SearchResult:
    return SearchResult(
        slide_id=slide_id,
        course="Physics",
        source_file="lecture.pdf",
        source_path="/courses/Physics/lecture.pdf",
        source_status="ready",
        source_error=None,
        ordinal=slide_id,
        kind="page",
        title=f"Topic {slide_id}",
        body_text=raw_text,
        speaker_notes="",
        raw_text=raw_text,
        extraction_status="review-needed",
        extraction_reasons=("embedded-image",),
        native_text_chars=len(raw_text),
        has_visual_content=True,
        visual_description=None,
        render_path="/render.png",
        vision_status="pending",
        ocr_text=None,
        ocr_confidence=None,
        ocr_backend=None,
        ocr_status="pending",
        snippet="query-centered evidence",
        score=1.0,
        lexical_coverage=1.0,
        lexical_title_matches=1,
        lexical_phrase_match=True,
    )


def _serialized_size(value: object) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
        )
    )


def test_compact_search_deduplicates_sources_and_preserves_required_metadata():
    payload = search_response(
        [_result(slide_id=1), _result(slide_id=2)],
        warnings=[{"type": "extraction_review_needed"}],
        sync_required=False,
        suggested_terms=[],
    )

    assert list(payload["sources"]) == ["s1"]
    assert {item["source_id"] for item in payload["results"]} == {"s1"}
    assert [item["rank"] for item in payload["results"]] == [1, 2]
    assert all(item["citation"] for item in payload["results"])
    assert all(item["extraction_status"] for item in payload["results"])
    assert payload["continuation"]["type"] == "read_selected"
    assert payload["warnings"] == [{"type": "extraction_review_needed"}]
    assert payload["estimated_tokens"] == estimate_tokens(payload)


def test_tiny_budget_removes_evidence_before_required_metadata():
    payload = search_response(
        [_result(raw_text="x" * 10_000)],
        warnings=[{"type": "required-warning", "message": "keep me"}],
        sync_required=False,
        suggested_terms=[],
        budget_tokens=1,
    )

    result = payload["results"][0]
    assert payload["budget_exhausted"] is True
    assert payload["warnings"][0]["message"] == "keep me"
    assert result["citation"] == "[Physics, lecture.pdf, Page 1]"
    assert result["extraction_reasons"] == ("embedded-image",)
    assert result["evidence"] == ""


def test_normal_focused_payload_is_at_least_sixty_percent_smaller():
    results = [
        _result(slide_id=1, raw_text="concept explanation " * 80),
        _result(slide_id=2, raw_text="worked example " * 80),
    ]
    compact = search_response(
        results,
        warnings=[],
        sync_required=False,
        suggested_terms=[],
    )
    full = search_response(
        results,
        warnings=[],
        sync_required=False,
        suggested_terms=[],
        full=True,
    )
    assert _serialized_size(compact) < _serialized_size(full) * 0.4


def test_full_search_is_lossless_and_ignores_response_budget():
    raw_text = "x" * 10_000
    payload = search_response(
        [_result(raw_text=raw_text)],
        warnings=[],
        sync_required=False,
        suggested_terms=[],
        full=True,
    )

    assert payload["compact"] is False
    assert payload["budget_tokens"] is None
    assert payload["budget_exhausted"] is False
    assert payload["results"][0]["raw_text"] == raw_text
