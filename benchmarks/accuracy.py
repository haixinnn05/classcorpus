from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

import fitz

from benchmarks.generate import png_bytes
from classcorpus.citations import format_citation
from classcorpus.claims import check_claims
from classcorpus.database import Database
from classcorpus.indexer import sync_course
from classcorpus.search import search

ACCURACY_MANIFEST_PATH = Path(__file__).with_name("accuracy_manifest.json")
RETRIEVAL_LIMIT = 5


def load_accuracy_manifest() -> dict[str, Any]:
    return json.loads(ACCURACY_MANIFEST_PATH.read_text(encoding="utf-8"))


def generate_accuracy_corpus(
    output_dir: Path,
) -> dict[str, dict[str, Path]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: dict[str, dict[str, Path]] = {}

    physics = output_dir / "physics"
    generated["Physics"] = {
        "kinematics.md": _write(
            physics / "kinematics.md",
            """# Constant-Acceleration Kinematics

For motion with constant acceleration, the relation
v^2 = v0^2 + 2a delta x connects velocity and displacement without time.
The equation is valid only while acceleration remains constant.
""",
        ),
        "vectors.md": _write(
            physics / "vectors.md",
            """# Vector Components

For an angle measured counterclockwise from the positive x-axis, the vector
components are r_x = r cosine theta and r_y = r sine theta. Component signs
must match the vector's quadrant.
""",
        ),
        "physics-glossary.txt": _write(
            physics / "physics-glossary.txt",
            "Motion acceleration time displacement vector equation. " * 24,
        ),
    }

    history = output_dir / "history"
    generated["History"] = {
        "reconstruction.md": _write(
            history / "reconstruction.md",
            """# Reconstruction Institutions

The Freedmen's Bureau supported schools, supervised labor contracts, and
provided medical care. Its work was substantial but constrained by limited
funding, political opposition, and the scale of postwar need.
""",
        ),
        "industrialization.md": _write(
            history / "industrialization.md",
            """# Early Industrial Labor

The Lowell mills recruited young women into textile wage labor and housed many
workers in company boardinghouses. Factory schedules reorganized work around
the clock rather than household production rhythms.
""",
        ),
        "history-glossary.txt": _write(
            history / "history-glossary.txt",
            "Institutions labor political work schools factory history. " * 24,
        ),
    }

    biology = output_dir / "biology"
    generated["Biology"] = {
        "cell-transport.md": _write(
            biology / "cell-transport.md",
            """# Membrane Transport

Osmosis is the net movement of water across a selectively semipermeable
membrane down its water concentration gradient. Solute concentration affects
the direction of net water movement.
""",
        ),
        "enzyme-revision.md": _write(
            biology / "enzyme-revision.md",
            """# Enzyme Temperature Revision

An initial pilot suggested an optimum near 40 degrees Celsius. The revised
experiment used more replicates, invalidated that estimate, and found the
enzyme optimum at 32 degrees Celsius.
""",
        ),
        "biology-glossary.txt": _write(
            biology / "biology-glossary.txt",
            "Cell membrane concentration enzyme water experiment biology. " * 24,
        ),
        "membrane-diagram.pdf": _make_visual_pdf(biology / "membrane-diagram.pdf"),
    }
    return generated


def run_accuracy_benchmark(
    database: Database,
    *,
    corpus_dir: Path,
) -> dict[str, Any]:
    manifest = load_accuracy_manifest()
    generated = generate_accuracy_corpus(corpus_dir)
    sync_reports = {
        course: sync_course(database, course, corpus_dir / course.casefold())
        for course in manifest["courses"]
    }
    retrieval = _evaluate_retrieval(database, manifest)
    synthesis = _evaluate_synthesis(database, manifest)
    unanswerable = _evaluate_unanswerable(database, manifest)
    claims = _evaluate_claims(database, manifest, corpus_dir / "claim-inputs")
    visual_review = _evaluate_visual_review(database, manifest)
    failures: list[dict[str, Any]] = []
    failures.extend(
        {
            "category": "index",
            "course": course,
            "failed_sources": report.failed,
        }
        for course, report in sync_reports.items()
        if report.failed
    )
    for category, result in (
        ("retrieval", retrieval),
        ("synthesis", synthesis),
        ("unanswerable", unanswerable),
        ("claims", claims),
        ("visual_review", visual_review),
    ):
        failures.extend(
            {"category": category, **failure} for failure in result["failures"]
        )
    return {
        "passed": not failures,
        "benchmark_version": manifest["version"],
        "courses": len(generated),
        "sources": sum(len(sources) for sources in generated.values()),
        "index": {
            course: {
                "indexed": report.indexed,
                "failed": report.failed,
                "records_indexed": report.records_indexed,
                "records_review_needed": report.records_review_needed,
            }
            for course, report in sync_reports.items()
        },
        "retrieval": retrieval,
        "synthesis": synthesis,
        "unanswerable": unanswerable,
        "claims": claims,
        "visual_review": visual_review,
        "failures": failures,
    }


def _evaluate_retrieval(
    database: Database,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    reciprocal_ranks: list[float] = []
    top_ranked = 0
    citations_correct = 0
    successful = 0
    for case in manifest["retrieval_cases"]:
        results = search(
            database,
            str(case["query"]),
            course=str(case["course"]),
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
        successful += int(rank is not None)
        top_ranked += int(rank == 1)
        expected_citation = (
            f"[{case['course']}, {case['source']}, Page {case['ordinal']}]"
        )
        actual_citation = (
            format_citation(results[rank - 1]) if rank is not None else None
        )
        citations_correct += int(actual_citation == expected_citation)
        reciprocal_ranks.append(0.0 if rank is None else 1.0 / rank)
        if rank != 1:
            failures.append(
                {
                    "id": case["id"],
                    "expected": case["source"],
                    "rank": rank,
                    "expected_citation": expected_citation,
                    "actual_citation": actual_citation,
                    "returned": [result.source_file for result in results],
                }
            )
    total = len(manifest["retrieval_cases"])
    return {
        "passed": not failures,
        "cases": total,
        "recall_at_5": successful / total if total else 1.0,
        "top_1_accuracy": top_ranked / total if total else 1.0,
        "citation_accuracy": citations_correct / total if total else 1.0,
        "mean_reciprocal_rank": (sum(reciprocal_ranks) / total if total else 1.0),
        "failures": failures,
    }


def _evaluate_synthesis(
    database: Database,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    covered = 0
    for case in manifest["synthesis_cases"]:
        results = search(
            database,
            str(case["query"]),
            course=str(case["course"]),
            limit=RETRIEVAL_LIMIT,
        )
        returned = {result.source_file for result in results}
        expected = set(case["sources"])
        complete = expected.issubset(returned)
        covered += int(complete)
        if not complete:
            failures.append(
                {
                    "id": case["id"],
                    "expected": sorted(expected),
                    "returned": sorted(returned),
                }
            )
    total = len(manifest["synthesis_cases"])
    return {
        "passed": not failures,
        "cases": total,
        "coverage_accuracy": covered / total if total else 1.0,
        "failures": failures,
    }


def _evaluate_unanswerable(
    database: Database,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    refused = 0
    for case in manifest["unanswerable_cases"]:
        results = search(
            database,
            str(case["query"]),
            course=str(case["course"]),
            limit=RETRIEVAL_LIMIT,
        )
        refused += int(not results)
        if results:
            failures.append(
                {
                    "id": case["id"],
                    "returned": [result.source_file for result in results],
                }
            )
    total = len(manifest["unanswerable_cases"])
    return {
        "passed": not failures,
        "cases": total,
        "refusal_accuracy": refused / total if total else 1.0,
        "failures": failures,
    }


def _evaluate_claims(
    database: Database,
    manifest: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    failures: list[dict[str, Any]] = []
    correct = 0
    for case in manifest["claim_cases"]:
        path = output_dir / f"{case['id']}.md"
        path.write_text(str(case["claim"]), encoding="utf-8")
        payload = check_claims(database, path)
        verdict = payload["claims"][0]["verdict"] if payload["claims"] else "missing"
        correct += int(verdict == case["expected"])
        if verdict != case["expected"]:
            failures.append(
                {
                    "id": case["id"],
                    "expected": case["expected"],
                    "actual": verdict,
                }
            )
    total = len(manifest["claim_cases"])
    return {
        "passed": not failures,
        "cases": total,
        "verdict_accuracy": correct / total if total else 1.0,
        "failures": failures,
    }


def _evaluate_visual_review(
    database: Database,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    correct = 0
    for case in manifest["visual_review_cases"]:
        row = database.connection.execute(
            """
            SELECT slides.extraction_status, slides.extraction_reasons
            FROM slides
            JOIN source_files ON source_files.id = slides.source_file_id
            JOIN courses ON courses.id = source_files.course_id
            WHERE courses.name = ? AND source_files.relative_path = ?
                  AND slides.ordinal = ?
            """,
            (case["course"], case["source"], case["ordinal"]),
        ).fetchone()
        actual = None
        if row is not None:
            actual = {
                "status": str(row["extraction_status"]),
                "reasons": json.loads(row["extraction_reasons"]),
            }
        expected = {"status": case["status"], "reasons": case["reasons"]}
        correct += int(actual == expected)
        if actual != expected:
            failures.append(
                {
                    "id": case["id"],
                    "expected": expected,
                    "actual": actual,
                }
            )
    total = len(manifest["visual_review_cases"])
    return {
        "passed": not failures,
        "cases": total,
        "accuracy": correct / total if total else 1.0,
        "failures": failures,
    }


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _make_visual_pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((72, 96), "Membrane", fontsize=18)
    page.insert_image(
        fitz.Rect(72, 132, 540, 600),
        stream=BytesIO(png_bytes()),
    )
    document.save(path)
    document.close()
    return path


__all__ = [
    "generate_accuracy_corpus",
    "load_accuracy_manifest",
    "run_accuracy_benchmark",
]
