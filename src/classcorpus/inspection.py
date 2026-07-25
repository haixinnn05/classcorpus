from __future__ import annotations

from dataclasses import asdict
import hashlib
from pathlib import Path
import shlex
from typing import Any, Literal

from classcorpus.database import Database
from classcorpus.indexer import PARSER_VERSION
from classcorpus.payloads import with_estimated_tokens
from classcorpus.record_text import (
    RECORD_TEXT_FIELDS,
    RecordTextField,
    read_record_text,
)
from classcorpus.security import mark_untrusted_content

DEFAULT_INSPECT_CHARS = 1_200
SourceVerification = Literal[
    "current",
    "changed",
    "missing",
    "stale-parser",
    "unavailable",
]


def inspect_record(
    database: Database,
    *,
    course: str,
    source_file: str,
    ordinal: int,
    field: RecordTextField = "searchable",
    offset: int = 0,
    limit: int = DEFAULT_INSPECT_CHARS,
) -> dict[str, Any]:
    if field not in RECORD_TEXT_FIELDS:
        raise ValueError(
            "field must be one of: " + ", ".join(RECORD_TEXT_FIELDS)
        )
    chunk = read_record_text(
        database,
        course=course,
        source_file=source_file,
        ordinal=ordinal,
        field=field,
        offset=offset,
        limit=limit,
    )
    row = database.connection.execute(
        """
        SELECT source_files.sha256, source_files.parser_version,
               slides.render_path, slides.has_visual_content
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        WHERE slides.id = ?
        """,
        (chunk.slide_id,),
    ).fetchone()
    assert row is not None

    verification, current_sha256, verification_error = _verify_source(
        Path(chunk.source_path),
        indexed_sha256=str(row["sha256"]),
        indexed_parser_version=str(row["parser_version"]),
    )
    render_path = (
        str(row["render_path"]) if row["render_path"] is not None else None
    )
    render_available = bool(render_path and Path(render_path).is_file())
    assets = [
        {
            **asdict(asset),
            "available": Path(asset.path).is_file(),
        }
        for asset in database.visual_assets_for_slide(chunk.slide_id)
    ]
    warnings = _warnings(
        chunk=chunk,
        verification=verification,
        verification_error=verification_error,
        has_visual_content=bool(row["has_visual_content"]),
        preview_available=render_available
        or any(bool(asset["available"]) for asset in assets),
    )
    continuation = None
    if chunk.next_offset is not None:
        continuation = {
            "next_offset": chunk.next_offset,
            "command": shlex.join(
                [
                    "classcorpus",
                    "inspect",
                    chunk.course,
                    chunk.source_file,
                    str(chunk.ordinal),
                    "--field",
                    chunk.field,
                    "--offset",
                    str(chunk.next_offset),
                    "--limit",
                    str(limit),
                    "--json",
                ]
            ),
        }
    payload: dict[str, Any] = {
        "ok": True,
        **asdict(chunk),
        "source_verification": verification,
        "indexed_sha256": str(row["sha256"]),
        "current_sha256": current_sha256,
        "indexed_parser_version": str(row["parser_version"]),
        "current_parser_version": PARSER_VERSION,
        "render_path": render_path,
        "render_available": render_available,
        "visual_assets": assets,
        "warnings": warnings,
        "continuation": continuation,
    }
    mark_untrusted_content(payload)
    return with_estimated_tokens(payload)


def _verify_source(
    path: Path,
    *,
    indexed_sha256: str,
    indexed_parser_version: str,
) -> tuple[SourceVerification, str | None, str | None]:
    if not path.is_file():
        return "missing", None, None
    try:
        current_sha256 = _sha256(path)
    except OSError as error:
        return "unavailable", None, str(error)
    if current_sha256 != indexed_sha256:
        return "changed", current_sha256, None
    if indexed_parser_version != PARSER_VERSION:
        return "stale-parser", current_sha256, None
    return "current", current_sha256, None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _warnings(
    *,
    chunk,
    verification: SourceVerification,
    verification_error: str | None,
    has_visual_content: bool,
    preview_available: bool,
) -> list[dict[str, object]]:
    warnings: list[dict[str, object]] = []
    messages = {
        "changed": (
            "The source changed after indexing. Synchronize the course before "
            "relying on this stored evidence."
        ),
        "missing": (
            "The indexed source file is missing. Restore it or remove the course."
        ),
        "stale-parser": (
            "The parser changed after indexing. Synchronize the course before "
            "relying on this stored evidence."
        ),
        "unavailable": "The source could not be read for freshness verification.",
    }
    if verification != "current":
        warning: dict[str, object] = {
            "type": f"source_{verification.replace('-', '_')}",
            "message": messages[verification],
        }
        if verification_error is not None:
            warning["error"] = verification_error
        warnings.append(warning)
    if chunk.source_status == "failed":
        warnings.append(
            {
                "type": "source_failed",
                "message": chunk.source_error or "The latest refresh failed.",
            }
        )
    if chunk.extraction_status == "review-needed":
        warnings.append(
            {
                "type": "extraction_review_needed",
                "reasons": list(chunk.extraction_reasons),
                "message": "Native extraction may not represent all content.",
            }
        )
    if has_visual_content and not preview_available:
        warnings.append(
            {
                "type": "visual_preview_unavailable",
                "message": "No local render or embedded visual asset is available.",
            }
        )
    return warnings


__all__ = [
    "DEFAULT_INSPECT_CHARS",
    "SourceVerification",
    "inspect_record",
]
