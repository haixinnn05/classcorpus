from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

from classcorpus.database import Database
from classcorpus.indexer import sync_course
from classcorpus.search import search

COURSE = "SCALE-SEMESTER-101"
MARKDOWN_SOURCES = 160
TRANSCRIPT_SOURCES = 20
CUES_PER_TRANSCRIPT = 20
EXPECTED_SOURCES = MARKDOWN_SOURCES + TRANSCRIPT_SOURCES
EXPECTED_RECORDS = MARKDOWN_SOURCES + TRANSCRIPT_SOURCES * CUES_PER_TRANSCRIPT
INDEX_SECONDS_LIMIT = 15.0
INCREMENTAL_SECONDS_LIMIT = 3.0
QUERY_MEDIAN_MS_LIMIT = 100.0
QUERY_P95_MS_LIMIT = 500.0


def run_scale_benchmark(work_dir: Path | None = None) -> dict[str, Any]:
    if work_dir is None:
        with tempfile.TemporaryDirectory(prefix="classcorpus-scale-") as temporary:
            return _run(Path(temporary))
    return _run(work_dir.expanduser().resolve())


def _run(work_dir: Path) -> dict[str, Any]:
    root = work_dir / "corpus"
    database_path = work_dir / "classcorpus.sqlite3"
    _generate_semester(root)
    database = Database(database_path)
    database.initialize()

    started = perf_counter()
    indexed = sync_course(database, COURSE, root)
    index_seconds = perf_counter() - started

    started = perf_counter()
    incremental = sync_course(database, COURSE, root)
    incremental_seconds = perf_counter() - started

    failures: list[dict[str, object]] = []
    query_times_ms: list[float] = []
    for query, expected_source, expected_ordinal in _query_cases():
        started = perf_counter()
        results = search(database, query, course=COURSE, limit=5)
        query_times_ms.append((perf_counter() - started) * 1000)
        actual = (results[0].source_file, results[0].ordinal) if results else None
        expected = (expected_source, expected_ordinal)
        if actual != expected:
            failures.append(
                {
                    "query": query,
                    "expected": expected,
                    "actual": actual,
                }
            )

    ordered = sorted(query_times_ms)
    p95_index = max(0, min(len(ordered) - 1, int(len(ordered) * 0.95) - 1))
    query_median_ms = median(ordered)
    query_p95_ms = ordered[p95_index]
    checks = {
        "source_count": database.source_health(COURSE).ready == EXPECTED_SOURCES,
        "record_count": database.slide_count(COURSE) == EXPECTED_RECORDS,
        "index_succeeded": indexed.failed == 0,
        "incremental_skipped_all": (
            incremental.failed == 0
            and incremental.indexed == 0
            and incremental.skipped == EXPECTED_SOURCES
        ),
        "retrieval_exact": not failures,
        "index_time": index_seconds <= INDEX_SECONDS_LIMIT,
        "incremental_time": incremental_seconds <= INCREMENTAL_SECONDS_LIMIT,
        "query_median": query_median_ms <= QUERY_MEDIAN_MS_LIMIT,
        "query_p95": query_p95_ms <= QUERY_P95_MS_LIMIT,
        "database_integrity": (
            database.connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        ),
    }
    return {
        "ok": all(checks.values()),
        "tier": "realistic-semester",
        "course": COURSE,
        "sources": EXPECTED_SOURCES,
        "records": EXPECTED_RECORDS,
        "queries": len(query_times_ms),
        "metrics": {
            "index_seconds": round(index_seconds, 4),
            "incremental_seconds": round(incremental_seconds, 4),
            "query_median_ms": round(query_median_ms, 3),
            "query_p95_ms": round(query_p95_ms, 3),
        },
        "thresholds": {
            "index_seconds": INDEX_SECONDS_LIMIT,
            "incremental_seconds": INCREMENTAL_SECONDS_LIMIT,
            "query_median_ms": QUERY_MEDIAN_MS_LIMIT,
            "query_p95_ms": QUERY_P95_MS_LIMIT,
        },
        "checks": checks,
        "failures": failures,
    }


def _generate_semester(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for index in range(MARKDOWN_SOURCES):
        marker = f"concept{index:03d}"
        (root / f"notes-{index:03d}.md").write_text(
            f"# Week {index + 1} {marker}\n\n"
            f"The {marker} principle explains conservation in this unit.\n"
            "Students compare evidence, assumptions, and worked examples.\n"
            + ("Practice retrieval with spaced review. " * 30),
            encoding="utf-8",
        )
    for source_index in range(TRANSCRIPT_SOURCES):
        blocks = ["WEBVTT"]
        for cue_index in range(CUES_PER_TRANSCRIPT):
            start = cue_index * 10
            marker = f"transcript{source_index:03d}cue{cue_index:03d}"
            blocks.append(
                f"00:{start // 60:02d}:{start % 60:02d}.000 --> "
                f"00:{(start + 5) // 60:02d}:{(start + 5) % 60:02d}.000\n"
                f"The {marker} example connects impulse and momentum."
            )
        (root / f"recording-{source_index:03d}.vtt").write_text(
            "\n\n".join(blocks) + "\n",
            encoding="utf-8",
        )


def _query_cases() -> list[tuple[str, str, int]]:
    cases = [
        (f"concept{index:03d} conservation", f"notes-{index:03d}.md", 1)
        for index in range(0, MARKDOWN_SOURCES, 8)
    ]
    cases.extend(
        (
            f"transcript{source_index:03d}cue{cue_index:03d} momentum",
            f"recording-{source_index:03d}.vtt",
            cue_index + 1,
        )
        for source_index in range(0, TRANSCRIPT_SOURCES, 2)
        for cue_index in (3, 17)
    )
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the realistic-semester ClassCorpus scale benchmark."
    )
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()
    result = run_scale_benchmark(arguments.work_dir)
    if arguments.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        metrics = result["metrics"]
        print(
            f"Scale: {result['sources']} sources, {result['records']} records; "
            f"index {metrics['index_seconds']:.3f}s; "
            f"query p95 {metrics['query_p95_ms']:.1f}ms"
        )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["run_scale_benchmark"]
