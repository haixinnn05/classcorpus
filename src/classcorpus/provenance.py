from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from html.parser import HTMLParser
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import fitz

from classcorpus.citations import (
    CITATION_PATTERN,
    format_record_citation,
    logical_record_kind,
)
from classcorpus.database import Database

MANIFEST_SUFFIX = ".classcorpus.json"
MANIFEST_VERSION = 1


def manifest_path(artifact: Path) -> Path:
    return artifact.with_name(artifact.name + MANIFEST_SUFFIX)


def write_artifact_manifest(
    database: Database,
    *,
    artifact: Path,
    citation_source: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    artifact = artifact.expanduser().resolve()
    citation_source = citation_source.expanduser().resolve()
    if not artifact.is_file():
        raise ValueError(f"artifact is not a file: {artifact}")
    if not citation_source.is_file():
        raise ValueError(f"citation source is not a file: {citation_source}")
    target = manifest_path(artifact)
    if target.exists() and not overwrite:
        raise FileExistsError(
            f"manifest already exists: {target}; pass --overwrite to replace it"
        )

    citations = _extract_citations(citation_source)
    records, unresolved = _resolve_citations(database, citations)
    sources: dict[tuple[str, str], dict[str, object]] = {}
    for record in records:
        key = (str(record["course"]), str(record["source_file"]))
        sources[key] = {
            "course": record["course"],
            "source_file": record["source_file"],
            "indexed_sha256": record["indexed_sha256"],
            "parser_version": record["parser_version"],
        }
    payload: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "classcorpus_version": _package_version(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifact": artifact.name,
        "artifact_sha256": _sha256(artifact),
        "citation_source": citation_source.name,
        "citation_source_sha256": _sha256(citation_source),
        "citations": records,
        "sources": list(sources.values()),
        "unresolved_citations": unresolved,
    }
    _write_json_atomic(target, payload)
    return {"manifest": str(target), **payload}


def verify_artifact(
    database: Database,
    artifact: Path,
) -> dict[str, Any]:
    artifact = artifact.expanduser().resolve()
    target = manifest_path(artifact)
    if not target.is_file():
        raise ValueError(f"artifact manifest not found: {target}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    issues: list[dict[str, str]] = []
    if not artifact.is_file():
        issues.append({"type": "artifact_missing", "message": "Artifact is missing."})
        delivery = None
    else:
        if _sha256(artifact) != payload.get("artifact_sha256"):
            issues.append(
                {"type": "artifact_modified", "message": "Artifact hash changed."}
            )
        delivery = inspect_artifact(artifact)
        if not delivery["ok"]:
            issues.append(
                {
                    "type": "artifact_unreadable",
                    "message": str(delivery["error"]),
                }
            )

    for source in payload.get("sources", []):
        row = database.connection.execute(
            """
            SELECT source_files.source_path
            FROM source_files
            JOIN courses ON courses.id = source_files.course_id
            WHERE courses.name = ? AND source_files.relative_path = ?
            """,
            (source["course"], source["source_file"]),
        ).fetchone()
        label = f"{source['course']}: {source['source_file']}"
        if row is None:
            issues.append(
                {
                    "type": "source_unindexed",
                    "message": f"Source is no longer indexed: {label}",
                }
            )
            continue
        source_path = Path(str(row["source_path"]))
        if not source_path.is_file():
            issues.append(
                {
                    "type": "source_missing",
                    "message": f"Source file is missing: {label}",
                }
            )
        elif _sha256(source_path) != source["indexed_sha256"]:
            issues.append(
                {
                    "type": "source_changed",
                    "message": f"Source file changed: {label}",
                }
            )
    if payload.get("unresolved_citations"):
        issues.append(
            {
                "type": "citation_unresolved",
                "message": "One or more citations were not found in the index.",
            }
        )

    issue_types = {issue["type"] for issue in issues}
    if "source_missing" in issue_types or "source_unindexed" in issue_types:
        status = "source-missing"
    elif "source_changed" in issue_types:
        status = "source-changed"
    elif "artifact_missing" in issue_types:
        status = "artifact-missing"
    elif "artifact_modified" in issue_types:
        status = "artifact-modified"
    elif "artifact_unreadable" in issue_types:
        status = "artifact-unreadable"
    elif "citation_unresolved" in issue_types:
        status = "unverified"
    else:
        status = "current"
    return {
        "ok": not issues,
        "status": status,
        "artifact": str(artifact),
        "manifest": str(target),
        "issues": issues,
        "delivery": delivery,
        "citations": payload.get("citations", []),
        "sources": payload.get("sources", []),
    }


def inspect_artifact(artifact: Path) -> dict[str, Any]:
    """Confirm that a delivered artifact can be decoded and rendered locally."""
    artifact = artifact.expanduser().resolve()
    if not artifact.is_file():
        return {
            "ok": False,
            "format": artifact.suffix.lower().lstrip(".") or "unknown",
            "error": f"Artifact is missing: {artifact}",
        }
    suffix = artifact.suffix.lower()
    try:
        if suffix == ".pdf":
            return _inspect_pdf(artifact)
        if suffix in {".html", ".htm"}:
            return _inspect_html(artifact)
        return {
            "ok": True,
            "format": suffix.lstrip(".") or "unknown",
            "bytes": artifact.stat().st_size,
        }
    except (OSError, UnicodeError, ValueError, fitz.FileDataError) as error:
        return {
            "ok": False,
            "format": suffix.lstrip(".") or "unknown",
            "error": f"Artifact cannot be opened or rendered: {error}",
        }


def _inspect_pdf(artifact: Path) -> dict[str, Any]:
    document = fitz.open(artifact)
    try:
        if document.needs_pass:
            raise ValueError("PDF is encrypted")
        if document.page_count < 1:
            raise ValueError("PDF has no pages")
        text_chars = 0
        for page in document:
            text_chars += len(page.get_text())
            pixmap = page.get_pixmap(matrix=fitz.Matrix(0.25, 0.25), alpha=False)
            if pixmap.width < 1 or pixmap.height < 1:
                raise ValueError(f"PDF page {page.number + 1} did not render")
        return {
            "ok": True,
            "format": "pdf",
            "bytes": artifact.stat().st_size,
            "pages": document.page_count,
            "rendered_pages": document.page_count,
            "text_chars": text_chars,
        }
    finally:
        document.close()


class _ArtifactHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del tag, attrs
        self.elements += 1


def _inspect_html(artifact: Path) -> dict[str, Any]:
    content = artifact.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError("HTML is empty")
    if "\x00" in content:
        raise ValueError("HTML contains NUL bytes")
    parser = _ArtifactHTMLParser()
    parser.feed(content)
    parser.close()
    if parser.elements < 1:
        raise ValueError("HTML contains no elements")
    return {
        "ok": True,
        "format": "html",
        "bytes": artifact.stat().st_size,
        "elements": parser.elements,
    }


def _extract_citations(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return list(dict.fromkeys(CITATION_PATTERN.findall(text)))


def _resolve_citations(
    database: Database,
    citations: list[str],
) -> tuple[list[dict[str, object]], list[str]]:
    wanted = set(citations)
    resolved: list[dict[str, object]] = []
    rows = database.connection.execute(
        """
        SELECT courses.name AS course, source_files.relative_path AS source_file,
               source_files.sha256, source_files.parser_version,
               slides.ordinal, slides.kind, slides.start_ms, slides.end_ms
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        """
    ).fetchall()
    for row in rows:
        start_ms = int(row["start_ms"]) if row["start_ms"] is not None else None
        kind = logical_record_kind(str(row["kind"]), start_ms)
        citation = format_record_citation(
            course=str(row["course"]),
            source_file=str(row["source_file"]),
            kind=kind,
            ordinal=int(row["ordinal"]),
            start_ms=start_ms,
        )
        if citation not in wanted:
            continue
        resolved.append(
            {
                "citation": citation,
                "course": str(row["course"]),
                "source_file": str(row["source_file"]),
                "ordinal": int(row["ordinal"]),
                "kind": kind,
                "start_ms": start_ms,
                "end_ms": (int(row["end_ms"]) if row["end_ms"] is not None else None),
                "indexed_sha256": str(row["sha256"]),
                "parser_version": str(row["parser_version"]),
            }
        )
    resolved_by_citation = {str(item["citation"]) for item in resolved}
    return resolved, [
        citation for citation in citations if citation not in resolved_by_citation
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _package_version() -> str:
    try:
        return version("classcorpus")
    except PackageNotFoundError:
        return "unknown"


__all__ = [
    "CITATION_PATTERN",
    "MANIFEST_SUFFIX",
    "inspect_artifact",
    "manifest_path",
    "verify_artifact",
    "write_artifact_manifest",
]
