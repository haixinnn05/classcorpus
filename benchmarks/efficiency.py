from __future__ import annotations

from dataclasses import asdict
import math
from pathlib import Path
from statistics import median
from typing import Any

from classcorpus.database import Database
from classcorpus.indexer import sync_course
from classcorpus.payloads import estimate_tokens, search_response
from classcorpus.record_text import read_record_text
from classcorpus.search import search

EFFICIENCY_COURSE = "TOKEN-EFFICIENCY-101"
FOCUSED_CASE_COUNT = 30

ADAPTIVE_LIMIT = 3
ADAPTIVE_SEARCH_BUDGET = 600
ADAPTIVE_READ_CHARS = 1_200

STANDARD_LIMIT = 6
STANDARD_SEARCH_BUDGET = 1_200
STANDARD_READ_CHARS = 2_000

MIN_STANDARD_REDUCTION = 0.25
MIN_FULL_REDUCTION = 0.70
MAX_MEDIAN_TOKENS = 2_500
MAX_P95_TOKENS = 4_000


def generate_efficiency_corpus(
    output_dir: Path,
    *,
    case_count: int = FOCUSED_CASE_COUNT,
) -> list[dict[str, str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cases: list[dict[str, str]] = []
    shared_paragraph = (
        "Physics motion analysis connects position, velocity, acceleration, "
        "force, energy, momentum, vectors, units, graphs, and experimental "
        "evidence. Students compare models, identify assumptions, and explain "
        "how measured quantities support a conclusion. "
    )
    for index in range(1, case_count + 1):
        marker = f"focus{index:02d}"
        source = f"record-{index:02d}.md"
        title = f"Motion investigation {marker}"
        body = (
            f"# {title}\n\n"
            f"The unique retrieval marker for this record is {marker}. "
            f"It identifies investigation {index:02d}.\n\n"
            + shared_paragraph * 12
        )
        (output_dir / source).write_text(body, encoding="utf-8")
        cases.append(
            {
                "id": marker,
                "query": f"physics motion {marker}",
                "source": source,
            }
        )
    return cases


def run_token_efficiency_benchmark(
    database: Database,
    *,
    corpus_dir: Path,
    skill_path: Path,
) -> dict[str, Any]:
    cases = generate_efficiency_corpus(corpus_dir)
    index_report = sync_course(database, EFFICIENCY_COURSE, corpus_dir)
    skill_tokens = estimate_tokens(skill_path.read_text(encoding="utf-8"))

    adaptive = _evaluate_workflow(
        database,
        cases,
        skill_tokens=skill_tokens,
        limit=ADAPTIVE_LIMIT,
        search_budget=ADAPTIVE_SEARCH_BUDGET,
        read_chars=ADAPTIVE_READ_CHARS,
        full=False,
    )
    standard = _evaluate_workflow(
        database,
        cases,
        skill_tokens=skill_tokens,
        limit=STANDARD_LIMIT,
        search_budget=STANDARD_SEARCH_BUDGET,
        read_chars=STANDARD_READ_CHARS,
        full=False,
    )
    full = _evaluate_workflow(
        database,
        cases,
        skill_tokens=skill_tokens,
        limit=STANDARD_LIMIT,
        search_budget=STANDARD_SEARCH_BUDGET,
        read_chars=None,
        full=True,
    )

    standard_reduction = _reduction(
        adaptive["aggregate_context_tokens"],
        standard["aggregate_context_tokens"],
    )
    full_reduction = _reduction(
        adaptive["aggregate_context_tokens"],
        full["aggregate_context_tokens"],
    )
    checks = {
        "index_succeeded": index_report.failed == 0,
        "adaptive_recall_complete": adaptive["recall"] == 1.0,
        "adaptive_top_ranked": adaptive["top_1_accuracy"] == 1.0,
        "rank_quality_unchanged": (
            adaptive["recall"] == standard["recall"]
            and adaptive["top_1_accuracy"] == standard["top_1_accuracy"]
            and adaptive["mean_reciprocal_rank"]
            == standard["mean_reciprocal_rank"]
        ),
        "standard_reduction_met": standard_reduction >= MIN_STANDARD_REDUCTION,
        "full_reduction_met": full_reduction >= MIN_FULL_REDUCTION,
        "median_target_met": (
            adaptive["median_context_tokens"] <= MAX_MEDIAN_TOKENS
        ),
        "p95_target_met": adaptive["p95_context_tokens"] <= MAX_P95_TOKENS,
    }
    failures = [
        *[
            {"workflow": "adaptive", **failure}
            for failure in adaptive["failures"]
        ],
        *[
            {"workflow": "standard", **failure}
            for failure in standard["failures"]
        ],
        *[{"workflow": "full", **failure} for failure in full["failures"]],
    ]
    failures.extend(
        {"check": name, "actual": False}
        for name, passed in checks.items()
        if not passed
    )
    return {
        "passed": all(checks.values()),
        "focused_cases": len(cases),
        "skill_estimated_tokens": skill_tokens,
        "index": {
            "indexed": index_report.indexed,
            "failed": index_report.failed,
            "records_indexed": index_report.records_indexed,
        },
        "thresholds": {
            "minimum_standard_reduction": MIN_STANDARD_REDUCTION,
            "minimum_full_reduction": MIN_FULL_REDUCTION,
            "maximum_median_context_tokens": MAX_MEDIAN_TOKENS,
            "maximum_p95_context_tokens": MAX_P95_TOKENS,
        },
        "workflows": {
            "adaptive": adaptive,
            "standard": standard,
            "full": full,
        },
        "reductions": {
            "adaptive_vs_standard": standard_reduction,
            "adaptive_vs_full": full_reduction,
        },
        "checks": checks,
        "failures": failures,
    }


def percentile(values: list[int], percentile_value: float) -> int:
    if not values:
        raise ValueError("values must not be empty")
    if percentile_value <= 0 or percentile_value > 1:
        raise ValueError("percentile must be greater than 0 and at most 1")
    ordered = sorted(values)
    rank = math.ceil(percentile_value * len(ordered))
    return ordered[rank - 1]


def _evaluate_workflow(
    database: Database,
    cases: list[dict[str, str]],
    *,
    skill_tokens: int,
    limit: int,
    search_budget: int,
    read_chars: int | None,
    full: bool,
) -> dict[str, Any]:
    context_totals: list[int] = []
    reciprocal_ranks: list[float] = []
    failures: list[dict[str, Any]] = []
    successful_cases = 0
    top_ranked_cases = 0

    for case in cases:
        results = search(
            database,
            case["query"],
            course=EFFICIENCY_COURSE,
            limit=limit,
        )
        rank = next(
            (
                result_rank
                for result_rank, result in enumerate(results, start=1)
                if result.source_file == case["source"]
            ),
            None,
        )
        reciprocal_ranks.append(0.0 if rank is None else 1.0 / rank)
        if rank is not None:
            successful_cases += 1
        if rank == 1:
            top_ranked_cases += 1
        else:
            failures.append(
                {
                    "id": case["id"],
                    "expected_source": case["source"],
                    "rank": rank,
                    "returned_sources": [
                        result.source_file for result in results
                    ],
                }
            )

        search_payload = search_response(
            results,
            warnings=[],
            sync_required=False,
            suggested_terms=[],
            full=full,
            budget_tokens=search_budget,
        )
        total_tokens = skill_tokens + int(search_payload["estimated_tokens"])
        if read_chars is not None and results:
            selected = results[0]
            chunk = read_record_text(
                database,
                course=EFFICIENCY_COURSE,
                source_file=selected.source_file,
                ordinal=selected.ordinal,
                limit=read_chars,
            )
            read_payload = {"ok": True, **asdict(chunk)}
            total_tokens += estimate_tokens(read_payload)
        context_totals.append(total_tokens)

    case_count = len(cases)
    return {
        "limit": limit,
        "search_budget_tokens": None if full else search_budget,
        "read_limit_chars": read_chars,
        "full_search": full,
        "successful_cases": successful_cases,
        "top_ranked_cases": top_ranked_cases,
        "recall": successful_cases / case_count if case_count else 1.0,
        "top_1_accuracy": top_ranked_cases / case_count if case_count else 1.0,
        "mean_reciprocal_rank": (
            sum(reciprocal_ranks) / case_count if case_count else 1.0
        ),
        "median_context_tokens": median(context_totals) if context_totals else 0,
        "p95_context_tokens": percentile(context_totals, 0.95)
        if context_totals
        else 0,
        "aggregate_context_tokens": sum(context_totals),
        "failures": failures,
    }


def _reduction(smaller: int, larger: int) -> float:
    if larger <= 0:
        return 0.0
    return 1.0 - smaller / larger


__all__ = [
    "EFFICIENCY_COURSE",
    "FOCUSED_CASE_COUNT",
    "generate_efficiency_corpus",
    "percentile",
    "run_token_efficiency_benchmark",
]
