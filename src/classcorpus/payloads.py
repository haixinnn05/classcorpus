from __future__ import annotations

from classcorpus.citations import format_citation
from classcorpus.search import SearchResult


def compact_search_result(result: SearchResult) -> dict[str, object]:
    omitted_fields = (
        result.body_text,
        result.speaker_notes,
        result.raw_text,
        result.visual_description or "",
        result.ocr_text or "",
    )
    return {
        "compact": True,
        "slide_id": result.slide_id,
        "course": result.course,
        "source_file": result.source_file,
        "source_path": result.source_path,
        "source_status": result.source_status,
        "source_error": result.source_error,
        "ordinal": result.ordinal,
        "kind": result.kind,
        "title": result.title,
        "evidence": result.snippet,
        "extraction_status": result.extraction_status,
        "extraction_reasons": result.extraction_reasons,
        "native_text_chars": result.native_text_chars,
        "has_visual_content": result.has_visual_content,
        "render_available": result.render_path is not None,
        "visual_asset_count": len(result.visual_assets),
        "vision_status": result.vision_status,
        "ocr_confidence": result.ocr_confidence,
        "ocr_backend": result.ocr_backend,
        "ocr_status": result.ocr_status,
        "score": result.score,
        "lexical_coverage": result.lexical_coverage,
        "lexical_title_matches": result.lexical_title_matches,
        "lexical_phrase_match": result.lexical_phrase_match,
        "citation": format_citation(result),
        "omitted_content_chars": sum(len(value) for value in omitted_fields),
    }


__all__ = ["compact_search_result"]

