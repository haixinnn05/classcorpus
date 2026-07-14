from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from classcorpus.database import Database
from classcorpus.models import SourceFingerprint
from classcorpus.parsers import parse_source
from classcorpus.paths import render_directory

PARSER_VERSION = "1"
SUPPORTED_SUFFIXES = {".pdf", ".pptx"}


@dataclass(frozen=True, slots=True)
class SyncReport:
    indexed: int
    skipped: int
    failed: int
    failures: tuple[dict[str, str], ...]


def fingerprint(path: Path) -> SourceFingerprint:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    stat = path.stat()
    return SourceFingerprint(
        size=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        sha256=digest.hexdigest(),
        parser_version=PARSER_VERSION,
    )


def sync_course(
    database: Database,
    name: str,
    source_root: Path,
) -> SyncReport:
    root = source_root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"course source root is not a directory: {root}")

    course = database.upsert_course(name, root)
    indexed = skipped = failed = 0
    failures: list[dict[str, str]] = []

    sources = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    for source in sources:
        relative_path = source.relative_to(root).as_posix()
        current_fingerprint = fingerprint(source)
        if database.source_is_current(
            course.id,
            relative_path,
            current_fingerprint,
        ):
            skipped += 1
            continue

        try:
            slides = parse_source(
                source,
                render_directory(name, current_fingerprint.sha256),
            )
            database.replace_source(
                course.id,
                relative_path,
                source,
                current_fingerprint,
                slides,
            )
        except Exception as error:
            database.record_source_error(
                course.id,
                relative_path,
                source,
                current_fingerprint,
                str(error),
            )
            failed += 1
            failures.append(
                {
                    "path": str(source),
                    "error": str(error),
                    "type": type(error).__name__,
                }
            )
        else:
            indexed += 1

    return SyncReport(
        indexed=indexed,
        skipped=skipped,
        failed=failed,
        failures=tuple(failures),
    )


__all__ = ["PARSER_VERSION", "SyncReport", "fingerprint", "sync_course"]
