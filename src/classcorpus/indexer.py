from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from classcorpus.database import Database
from classcorpus.models import SourceFingerprint
from classcorpus.parsers import parse_source
from classcorpus.paths import create_render_generation

PARSER_VERSION = "3"
SUPPORTED_SUFFIXES = {".pdf", ".pptx"}


@dataclass(frozen=True, slots=True)
class SyncReport:
    indexed: int
    skipped: int
    failed: int
    records_indexed: int
    records_review_needed: int
    failures: tuple[dict[str, str], ...]
    warnings: tuple[dict[str, object], ...]


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
    records_indexed = records_review_needed = 0
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, object]] = []

    sources = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    present_relative_paths = {
        source.relative_to(root).as_posix()
        for source in sources
    }
    _, cleanup_warnings = database.remove_missing_sources(
        course.id,
        present_relative_paths,
    )
    warnings.extend(cleanup_warnings)
    for source in sources:
        relative_path = source.relative_to(root).as_posix()
        current_fingerprint: SourceFingerprint | None = None
        render_dir: Path | None = None
        source_warnings: list[dict[str, object]] = []
        try:
            current_fingerprint = fingerprint(source)
            if database.source_is_current(
                course.id,
                relative_path,
                current_fingerprint,
                source,
            ):
                skipped += 1
                continue

            render_dir = create_render_generation(
                name,
                current_fingerprint.sha256,
                current_fingerprint.parser_version,
            )
            slides = parse_source(
                source,
                render_dir,
            )
            source_records_review_needed = 0
            for slide in slides:
                if slide.extraction_status == "review-needed":
                    source_records_review_needed += 1
                    source_warnings.append(
                        {
                            "path": str(source),
                            "ordinal": str(slide.ordinal),
                            "type": "extraction_review_needed",
                            "reasons": list(slide.extraction_reasons),
                            "message": (
                                f"{slide.kind.title()} {slide.ordinal} may "
                                "contain content that native extraction did "
                                "not fully capture."
                            ),
                        }
                    )
                    if (
                        source.suffix.lower() == ".pptx"
                        and slide.render_path is None
                        and not slide.visual_assets
                    ):
                        source_warnings.append(
                            {
                                "path": str(source),
                                "ordinal": str(slide.ordinal),
                                "type": "visual-source-unavailable",
                                "message": (
                                    "PowerPoint layout was not rendered. Export "
                                    "the lecture to PDF for pixel-accurate "
                                    "visual review."
                                ),
                            }
                        )
            if not any(
                slide.render_path or slide.visual_assets
                for slide in slides
            ):
                source_warnings.extend(
                    database.cleanup_render_directories({render_dir})
                )
            source_warnings.extend(
                database.replace_source(
                    course.id,
                    relative_path,
                    source,
                    current_fingerprint,
                    slides,
                )
            )
            records_indexed += len(slides)
            records_review_needed += source_records_review_needed
        except Exception as error:
            if render_dir is not None:
                warnings.extend(database.cleanup_render_directories({render_dir}))
            if current_fingerprint is None:
                database.mark_source_error(
                    course.id,
                    relative_path,
                    source,
                    PARSER_VERSION,
                    str(error),
                )
            else:
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
            warnings.extend(source_warnings)

    return SyncReport(
        indexed=indexed,
        skipped=skipped,
        failed=failed,
        records_indexed=records_indexed,
        records_review_needed=records_review_needed,
        failures=tuple(failures),
        warnings=tuple(warnings),
    )


__all__ = ["PARSER_VERSION", "SyncReport", "fingerprint", "sync_course"]
