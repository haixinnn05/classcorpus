from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, cast

from classcorpus.citations import format_record_citation
from classcorpus.claims import DEFAULT_SUPPORT_THRESHOLD, check_claims
from classcorpus.database import Database
from classcorpus.provenance import CITATION_PATTERN, manifest_path, verify_artifact
from classcorpus.record_text import RecordTextField
from classcorpus.security import mark_untrusted_content


def verify_study(
    database: Database,
    source: Path,
    *,
    artifact: Path | None = None,
    field: RecordTextField = "searchable",
    threshold: float = DEFAULT_SUPPORT_THRESHOLD,
    require_all_sources: bool = False,
) -> dict[str, Any]:
    """Combine claim, citation, source, coverage, and artifact checks."""
    source = source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"study source not found: {source}")

    claims = check_claims(
        database,
        source,
        field=field,
        threshold=threshold,
    )
    citations = _extract_citations(source)
    records, unresolved = _citation_records(database, citations)
    issues: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []

    if not citations:
        issues.append(
            {
                "type": "citation_missing",
                "message": "The study source contains no ClassCorpus citations.",
            }
        )
    for citation in unresolved:
        issues.append(
            {
                "type": "citation_unresolved",
                "citation": citation,
                "message": f"The citation is not indexed: {citation}",
            }
        )
    for claim in claims["claims"]:
        verdict = claim["verdict"]
        if verdict in {"unsupported", "unverified"}:
            issues.append(
                {
                    "type": f"{verdict}_claim",
                    "line": claim["line"],
                    "citation": claim["citation"],
                    "message": claim["message"],
                }
            )
        elif verdict == "weak":
            warnings.append(
                {
                    "type": "weak_claim",
                    "line": claim["line"],
                    "citation": claim["citation"],
                    "message": claim["message"],
                }
            )

    source_issues = _source_issues(records)
    issues.extend(source_issues)
    for record in records:
        if record["extraction_status"] != "review-needed":
            continue
        warnings.append(
            {
                "type": "extraction_review_needed",
                "citation": record["citation"],
                "reasons": record["extraction_reasons"],
                "message": (
                    "The cited record needs visual review before layout-dependent "
                    "claims are treated as complete."
                ),
            }
        )

    coverage = _source_coverage(database, records)
    for item in coverage:
        if item["complete"]:
            continue
        report = {
            "type": "source_coverage_incomplete",
            "course": item["course"],
            "missing_sources": item["missing_sources"],
            "message": (
                f"{item['represented_sources']}/{item['total_sources']} indexed "
                f"sources are represented for {item['course']}."
            ),
        }
        if require_all_sources:
            issues.append(report)
        else:
            warnings.append(report)

    for line in _uncited_prose(source):
        warnings.append(
            {
                "type": "uncited_prose",
                "line": line["line"],
                "text": line["text"],
                "message": "This prose line has no ClassCorpus citation.",
            }
        )

    artifact_reports = _artifact_reports(database, source, artifact)
    for report in artifact_reports:
        if report["ok"]:
            continue
        if report.get("issues"):
            issues.extend(cast(list[dict[str, object]], report["issues"]))
        else:
            issues.append(
                {
                    "type": "artifact_unverified",
                    "artifact": report["artifact"],
                    "message": report["error"],
                }
            )

    checks = {
        "citations_present": bool(citations),
        "citations_resolved": not unresolved,
        "claims_supported": bool(claims["ok"]),
        "sources_current": not source_issues,
        "source_coverage_complete": (
            all(item["complete"] for item in coverage) if require_all_sources else True
        ),
        "artifacts_current": all(bool(report["ok"]) for report in artifact_reports),
    }
    counts = claims["counts"]
    payload: dict[str, Any] = {
        "ok": all(checks.values()),
        "source": str(source),
        "checks": checks,
        "summary": {
            "cited_claims": claims["claims_total"],
            "supported_claims": counts["supported"],
            "weak_claims": counts["weak"],
            "unsupported_claims": counts["unsupported"],
            "unverified_claims": counts["unverified"],
            "citations": len(citations),
            "resolved_citations": len(records),
            "courses": len(coverage),
            "artifacts": len(artifact_reports),
            "warnings": len(warnings),
            "issues": len(issues),
        },
        "claims": claims,
        "citations": {
            "total": len(citations),
            "resolved": len(records),
            "unresolved": unresolved,
        },
        "coverage": coverage,
        "artifacts": artifact_reports,
        "warnings": warnings,
        "issues": issues,
        "method": (
            "Local deterministic verification. Claim support is lexical and is "
            "not proof of entailment; review weak claims and visual warnings."
        ),
    }
    return mark_untrusted_content(payload)


def _extract_citations(source: Path) -> list[str]:
    text = source.read_text(encoding="utf-8")
    return list(dict.fromkeys(CITATION_PATTERN.findall(text)))


def _citation_records(
    database: Database,
    citations: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    wanted = set(citations)
    records: list[dict[str, Any]] = []
    rows = database.connection.execute(
        """
        SELECT courses.name AS course,
               source_files.relative_path AS source_file,
               source_files.source_path,
               source_files.sha256,
               source_files.status AS source_status,
               slides.ordinal,
               slides.kind,
               slides.start_ms,
               slides.extraction_status,
               slides.extraction_reasons
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        """
    ).fetchall()
    for row in rows:
        citation = format_record_citation(
            course=str(row["course"]),
            source_file=str(row["source_file"]),
            kind=str(row["kind"]),
            ordinal=int(row["ordinal"]),
            start_ms=(int(row["start_ms"]) if row["start_ms"] is not None else None),
        )
        if citation not in wanted:
            continue
        records.append(
            {
                "citation": citation,
                "course": str(row["course"]),
                "source_file": str(row["source_file"]),
                "source_path": str(row["source_path"]),
                "indexed_sha256": str(row["sha256"]),
                "source_status": str(row["source_status"]),
                "extraction_status": str(row["extraction_status"]),
                "extraction_reasons": _json_list(row["extraction_reasons"]),
            }
        )
    resolved = {record["citation"] for record in records}
    unresolved = [citation for citation in citations if citation not in resolved]
    return records, unresolved


def _source_issues(records: list[dict[str, Any]]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (record["course"], record["source_file"])
        if key in seen:
            continue
        seen.add(key)
        label = f"{record['course']}: {record['source_file']}"
        path = Path(record["source_path"])
        if record["source_status"] != "ready":
            issues.append(
                {
                    "type": "source_failed",
                    "course": record["course"],
                    "source_file": record["source_file"],
                    "message": f"The latest indexed refresh failed: {label}",
                }
            )
        if not path.is_file():
            issues.append(
                {
                    "type": "source_missing",
                    "course": record["course"],
                    "source_file": record["source_file"],
                    "message": f"The cited source file is missing: {label}",
                }
            )
        elif _sha256(path) != record["indexed_sha256"]:
            issues.append(
                {
                    "type": "source_changed",
                    "course": record["course"],
                    "source_file": record["source_file"],
                    "message": f"The cited source changed after indexing: {label}",
                }
            )
    return issues


def _source_coverage(
    database: Database,
    records: list[dict[str, Any]],
) -> list[dict[str, object]]:
    represented: dict[str, set[str]] = {}
    for record in records:
        represented.setdefault(record["course"], set()).add(record["source_file"])
    coverage: list[dict[str, object]] = []
    for course, cited_sources in sorted(represented.items()):
        rows = database.connection.execute(
            """
            SELECT source_files.relative_path
            FROM source_files
            JOIN courses ON courses.id = source_files.course_id
            WHERE courses.name = ?
            ORDER BY source_files.relative_path
            """,
            (course,),
        ).fetchall()
        indexed_sources = [str(row["relative_path"]) for row in rows]
        missing = [name for name in indexed_sources if name not in cited_sources]
        coverage.append(
            {
                "course": course,
                "represented_sources": len(cited_sources),
                "total_sources": len(indexed_sources),
                "complete": not missing,
                "missing_sources": missing,
            }
        )
    return coverage


def _artifact_reports(
    database: Database,
    source: Path,
    artifact: Path | None,
) -> list[dict[str, Any]]:
    candidates = [artifact.expanduser().resolve()] if artifact is not None else []
    if artifact is None:
        for suffix in (".pdf", ".html"):
            candidate = source.with_suffix(suffix)
            if candidate.exists() or manifest_path(candidate).exists():
                candidates.append(candidate)
    reports: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            reports.append(verify_artifact(database, candidate))
        except (OSError, ValueError) as error:
            reports.append(
                {
                    "ok": False,
                    "status": "unverified",
                    "artifact": str(candidate),
                    "issues": [],
                    "error": str(error),
                }
            )
    return reports


def _uncited_prose(source: Path) -> list[dict[str, object]]:
    warnings: list[dict[str, object]] = []
    blocks = _prose_blocks(source.read_text(encoding="utf-8"))
    for index, (block, number) in enumerate(blocks):
        stripped = block.strip()
        if stripped.startswith(("#", "|", ">", "---", "***")):
            continue
        prose = CITATION_PATTERN.sub(" ", stripped).strip()
        if not prose:
            continue
        if CITATION_PATTERN.search(block):
            continue
        next_block = blocks[index + 1][0] if index + 1 < len(blocks) else ""
        next_prose = CITATION_PATTERN.sub(" ", next_block).strip()
        if CITATION_PATTERN.search(next_block) and not next_prose:
            continue
        prose = re.sub(r"^\s*(?:[-*+]\s+|\d+\.\s+)", "", prose)
        prose = re.sub(r"\s+", " ", prose)
        if len(re.findall(r"[A-Za-z]{2,}", prose)) < 5:
            continue
        warnings.append({"line": number, "text": prose[:240]})
    return warnings


def _prose_blocks(text: str) -> list[tuple[str, int]]:
    blocks: list[tuple[str, int]] = []
    lines: list[str] = []
    start = 1
    in_fence = False
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("```") and stripped != "```":
            if lines:
                blocks.append(("\n".join(lines), start))
                lines = []
            in_fence = True
            continue
        if stripped == "```":
            if lines:
                blocks.append(("\n".join(lines), start))
                lines = []
            in_fence = False
            continue
        if in_fence:
            continue
        if not stripped:
            if lines:
                blocks.append(("\n".join(lines), start))
                lines = []
            continue
        if not lines:
            start = number
        lines.append(raw)
    if lines:
        blocks.append(("\n".join(lines), start))
    return blocks


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_list(value: object) -> list[object]:
    loaded = json.loads(str(value))
    return list(loaded) if isinstance(loaded, list) else []


__all__ = ["verify_study"]
