from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from classcorpus.database import Database
from classcorpus.indexer import sync_course
from classcorpus.search import search

from benchmarks.generate import generate_corpus

MANIFEST_PATH = Path(__file__).with_name("manifest.json")
RETRIEVAL_LIMIT = 5


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def run_benchmark(work_dir: Path | None = None) -> dict[str, Any]:
    if work_dir is None:
        with tempfile.TemporaryDirectory(prefix="classcorpus-benchmark-") as temporary:
            return _run_benchmark(Path(temporary))
    work_dir.mkdir(parents=True, exist_ok=True)
    return _run_benchmark(work_dir.resolve())


def _run_benchmark(work_dir: Path) -> dict[str, Any]:
    manifest = load_manifest()
    corpus_dir = work_dir / "corpus"
    data_dir = work_dir / "data"
    generate_corpus(corpus_dir)

    previous_data_dir = os.environ.get("CLASSCORPUS_DATA_DIR")
    os.environ["CLASSCORPUS_DATA_DIR"] = str(data_dir)
    database = Database(work_dir / "benchmark.sqlite3")
    try:
        database.initialize()
        report = sync_course(database, str(manifest["course"]), corpus_dir)
        extraction = _evaluate_extraction(database, manifest)
        retrieval = _evaluate_retrieval(database, manifest)
    finally:
        database.connection.close()
        if previous_data_dir is None:
            os.environ.pop("CLASSCORPUS_DATA_DIR", None)
        else:
            os.environ["CLASSCORPUS_DATA_DIR"] = previous_data_dir

    ok = report.failed == 0 and extraction["passed"] and retrieval["passed"]
    return {
        "ok": ok,
        "benchmark_version": manifest["version"],
        "course": manifest["course"],
        "corpus": {
            "generated": True,
            "source_count": len(manifest["sources"]),
            "path": str(corpus_dir),
        },
        "index": {
            "indexed": report.indexed,
            "failed": report.failed,
            "records_indexed": report.records_indexed,
            "records_review_needed": report.records_review_needed,
        },
        "extraction": extraction,
        "retrieval": retrieval,
    }


def _evaluate_extraction(
    database: Database,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    source_counts = {
        str(row["relative_path"]): int(row["record_count"])
        for row in database.connection.execute(
            """
            SELECT source_files.relative_path, COUNT(slides.id) AS record_count
            FROM source_files
            LEFT JOIN slides ON slides.source_file_id = source_files.id
            GROUP BY source_files.id, source_files.relative_path
            """
        )
    }
    for source, expectation in manifest["sources"].items():
        actual = source_counts.get(source, 0)
        expected = int(expectation["record_count"])
        if actual != expected:
            failures.append(
                {
                    "id": f"record-count:{source}",
                    "expected": expected,
                    "actual": actual,
                }
            )

    rows = database.connection.execute(
        """
        SELECT source_files.relative_path, slides.ordinal, slides.title,
               slides.extraction_status, slides.extraction_reasons
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        """
    ).fetchall()
    records = {
        (str(row["relative_path"]), int(row["ordinal"])): row for row in rows
    }
    for case in manifest["extraction_cases"]:
        key = (str(case["source"]), int(case["ordinal"]))
        row = records.get(key)
        if row is None:
            failures.append({"id": case["id"], "error": "record missing"})
            continue
        actual = {
            "title": str(row["title"]),
            "status": str(row["extraction_status"]),
            "reasons": json.loads(row["extraction_reasons"]),
        }
        expected = {
            "title": case["title"],
            "status": case["status"],
            "reasons": case["reasons"],
        }
        if actual != expected:
            failures.append(
                {
                    "id": case["id"],
                    "expected": expected,
                    "actual": actual,
                }
            )

    total_cases = len(manifest["sources"]) + len(manifest["extraction_cases"])
    return {
        "passed": not failures,
        "cases": total_cases,
        "successful_cases": total_cases - len(failures),
        "failures": failures,
    }


def _evaluate_retrieval(
    database: Database,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    reciprocal_ranks: list[float] = []
    for case in manifest["retrieval_cases"]:
        results = search(
            database,
            str(case["query"]),
            course=str(manifest["course"]),
            limit=RETRIEVAL_LIMIT,
        )
        rank = next(
            (
                index
                for index, result in enumerate(results, start=1)
                if result.source_file == case["source"]
                and result.ordinal == int(case["ordinal"])
            ),
            None,
        )
        reciprocal_ranks.append(0.0 if rank is None else 1.0 / rank)
        if rank is None:
            failures.append(
                {
                    "id": case["id"],
                    "expected": {
                        "source": case["source"],
                        "ordinal": case["ordinal"],
                    },
                    "returned": [
                        {
                            "source": result.source_file,
                            "ordinal": result.ordinal,
                        }
                        for result in results
                    ],
                }
            )

    case_count = len(manifest["retrieval_cases"])
    successful_cases = case_count - len(failures)
    return {
        "passed": not failures,
        "limit": RETRIEVAL_LIMIT,
        "cases": case_count,
        "successful_cases": successful_cases,
        "recall_at_5": successful_cases / case_count if case_count else 1.0,
        "mean_reciprocal_rank": (
            sum(reciprocal_ranks) / case_count if case_count else 1.0
        ),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the reproducible ClassCorpus extraction/retrieval benchmark."
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="Keep generated corpus and index files in this directory.",
    )
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args()
    result = run_benchmark(arguments.work_dir)
    if arguments.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        extraction = result["extraction"]
        retrieval = result["retrieval"]
        print(
            f"Extraction: {extraction['successful_cases']}/{extraction['cases']}"
        )
        print(
            f"Retrieval recall@5: {retrieval['recall_at_5']:.3f}; "
            f"MRR: {retrieval['mean_reciprocal_rank']:.3f}"
        )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

