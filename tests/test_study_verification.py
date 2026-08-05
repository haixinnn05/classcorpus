import json
import os
import subprocess
import sys
from pathlib import Path

import fitz
import pytest

from classcorpus.database import Database
from classcorpus.indexer import sync_course
from classcorpus.provenance import write_artifact_manifest
from classcorpus.study_verification import verify_study

LECTURE_ONE = """# Shortest Paths

Bellman-Ford relaxes every edge V - 1 times. Its running time is O(V * E).
"""

LECTURE_TWO = """# Greedy Search

Dijkstra requires non-negative edge weights.
"""


@pytest.fixture
def study(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Database, Path, Path, Path]:
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "state"))
    course = tmp_path / "Algorithms"
    course.mkdir()
    first = course / "paths.md"
    first.write_text(LECTURE_ONE, encoding="utf-8")
    (course / "greedy.md").write_text(LECTURE_TWO, encoding="utf-8")
    database = Database()
    database.initialize()
    assert sync_course(database, "Algorithms", course).indexed == 2

    source = tmp_path / "guide.md"
    source.write_text(
        "Bellman-Ford relaxes every edge V - 1 times "
        "[Algorithms, paths.md, Page 1].\n"
        "Dijkstra requires non-negative edge weights "
        "[Algorithms, greedy.md, Page 1].\n",
        encoding="utf-8",
    )
    artifact = tmp_path / "guide.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Algorithms study guide")
    document.save(artifact)
    document.close()
    write_artifact_manifest(
        database,
        artifact=artifact,
        citation_source=source,
    )
    return database, source, artifact, first


def test_verify_study_combines_claim_source_coverage_and_artifact_checks(
    study: tuple[Database, Path, Path, Path],
):
    database, source, artifact, _ = study

    payload = verify_study(database, source, require_all_sources=True)

    assert payload["ok"] is True
    assert payload["summary"] == {
        "cited_claims": 2,
        "supported_claims": 2,
        "weak_claims": 0,
        "unsupported_claims": 0,
        "unverified_claims": 0,
        "citations": 2,
        "resolved_citations": 2,
        "courses": 1,
        "artifacts": 1,
        "warnings": 0,
        "issues": 0,
    }
    assert payload["coverage"][0]["represented_sources"] == 2
    assert payload["coverage"][0]["total_sources"] == 2
    assert payload["coverage"][0]["complete"] is True
    assert payload["artifacts"][0]["artifact"] == str(artifact.resolve())
    assert payload["artifacts"][0]["status"] == "current"


def test_verify_study_fails_an_unsupported_measurement(
    study: tuple[Database, Path, Path, Path],
):
    database, source, _, _ = study
    source.write_text(
        "Bellman-Ford runs in O(V log V) [Algorithms, paths.md, Page 1].\n",
        encoding="utf-8",
    )

    payload = verify_study(database, source)

    assert payload["ok"] is False
    assert payload["checks"]["claims_supported"] is False
    assert payload["claims"]["counts"]["unsupported"] == 1
    assert any(issue["type"] == "unsupported_claim" for issue in payload["issues"])


def test_verify_study_requires_at_least_one_citation(
    study: tuple[Database, Path, Path, Path],
):
    database, source, _, _ = study
    source.write_text("# Guide\n\nBellman-Ford is an algorithm.\n", encoding="utf-8")

    payload = verify_study(database, source)

    assert payload["ok"] is False
    assert payload["checks"]["citations_present"] is False
    assert any(issue["type"] == "citation_missing" for issue in payload["issues"])


def test_verify_study_detects_source_drift(
    study: tuple[Database, Path, Path, Path],
):
    database, source, _, lecture = study
    lecture.write_text("# Changed after indexing\n", encoding="utf-8")

    payload = verify_study(database, source)

    assert payload["ok"] is False
    assert payload["checks"]["sources_current"] is False
    assert any(issue["type"] == "source_changed" for issue in payload["issues"])


def test_verify_study_reports_review_and_uncited_prose_as_warnings(
    study: tuple[Database, Path, Path, Path],
):
    database, source, _, _ = study
    with database.connection:
        database.connection.execute(
            """
            UPDATE slides SET extraction_status = 'review-needed'
            WHERE id = (
                SELECT slides.id FROM slides
                JOIN source_files ON source_files.id = slides.source_file_id
                WHERE source_files.relative_path = 'paths.md'
            )
            """
        )
    source.write_text(
        "This introductory sentence has no citation.\n\n"
        "Bellman-Ford relaxes every edge V - 1 times "
        "[Algorithms, paths.md, Page 1].\n",
        encoding="utf-8",
    )

    payload = verify_study(database, source)

    assert payload["ok"] is True
    warning_types = {warning["type"] for warning in payload["warnings"]}
    assert "extraction_review_needed" in warning_types
    assert "uncited_prose" in warning_types


def test_verify_study_can_require_every_indexed_source(
    study: tuple[Database, Path, Path, Path],
):
    database, source, _, _ = study
    source.write_text(
        "Bellman-Ford relaxes every edge V - 1 times [Algorithms, paths.md, Page 1].\n",
        encoding="utf-8",
    )

    advisory = verify_study(database, source)
    required = verify_study(database, source, require_all_sources=True)

    assert advisory["ok"] is True
    assert advisory["coverage"][0]["missing_sources"] == ["greedy.md"]
    assert any(
        warning["type"] == "source_coverage_incomplete"
        for warning in advisory["warnings"]
    )
    assert required["ok"] is False
    assert required["checks"]["source_coverage_complete"] is False


def test_verify_study_detects_modified_auto_discovered_artifact(
    study: tuple[Database, Path, Path, Path],
):
    database, source, artifact, _ = study
    artifact.write_bytes(b"changed")

    payload = verify_study(database, source)

    assert payload["ok"] is False
    assert payload["checks"]["artifacts_current"] is False
    assert payload["artifacts"][0]["status"] == "artifact-modified"


def run_cli(*arguments: str, data_dir: Path, cwd: Path):
    environment = os.environ.copy()
    environment["CLASSCORPUS_DATA_DIR"] = str(data_dir)
    root = Path(__file__).resolve().parents[1]
    environment["PYTHONPATH"] = str(root / "src")
    return subprocess.run(
        [sys.executable, "-m", "classcorpus", *arguments],
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_verify_study_cli_has_json_and_human_reports(
    study: tuple[Database, Path, Path, Path],
    tmp_path: Path,
):
    _, source, _, _ = study
    data_dir = tmp_path / "state"

    json_result = run_cli(
        "verify-study",
        str(source),
        "--require-all-sources",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    human_result = run_cli(
        "verify-study",
        str(source),
        "--require-all-sources",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    payload = json.loads(json_result.stdout)
    assert json_result.returncode == 0, json_result.stderr
    assert payload["ok"] is True
    assert human_result.returncode == 0, human_result.stderr
    assert "VERIFIED" in human_result.stdout
    assert "2 cited claims" in human_result.stdout
    assert "2/2 sources represented" in human_result.stdout
