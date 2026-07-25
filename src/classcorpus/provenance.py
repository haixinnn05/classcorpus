from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from classcorpus.database import Database

MANIFEST_SUFFIX = ".classcorpus.json"
MANIFEST_VERSION = 1
_CITATION_PATTERN = re.compile(
    r"\[[^\]\n]+,\s*(?:Slide|Page)\s+\d+\]"
)


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
    elif _sha256(artifact) != payload.get("artifact_sha256"):
        issues.append(
            {"type": "artifact_modified", "message": "Artifact hash changed."}
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
        "citations": payload.get("citations", []),
        "sources": payload.get("sources", []),
    }


def _extract_citations(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return list(dict.fromkeys(_CITATION_PATTERN.findall(text)))


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
               slides.ordinal, slides.kind
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        """
    ).fetchall()
    for row in rows:
        label = "Slide" if row["kind"] == "slide" else "Page"
        citation = (
            f"[{row['course']}, {row['source_file']}, "
            f"{label} {row['ordinal']}]"
        )
        if citation not in wanted:
            continue
        resolved.append(
            {
                "citation": citation,
                "course": str(row["course"]),
                "source_file": str(row["source_file"]),
                "ordinal": int(row["ordinal"]),
                "kind": str(row["kind"]),
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
    "MANIFEST_SUFFIX",
    "manifest_path",
    "verify_artifact",
    "write_artifact_manifest",
]
