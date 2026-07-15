import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.fixtures.make_fixtures import make_pdf_fixture, make_pptx_fixture

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run_script(
    name: str,
    *arguments: str,
    data_dir: Path,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["CLASSCORPUS_DATA_DIR"] = str(data_dir)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *arguments],
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_index_and_search_scripts_return_json_from_any_working_directory(
    tmp_path: Path,
):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pdf_fixture(course / "handout.pdf")
    data_dir = tmp_path / "state"
    unrelated_cwd = tmp_path / "elsewhere"
    unrelated_cwd.mkdir()

    indexed = run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=unrelated_cwd,
    )
    searched = run_script(
        "search_lectures.py",
        "negative edges",
        "--course",
        "Algorithms",
        "--json",
        data_dir=data_dir,
        cwd=unrelated_cwd,
    )

    assert indexed.returncode == 0, indexed.stderr
    assert json.loads(indexed.stdout)["indexed"] == 1
    assert searched.returncode == 0, searched.stderr
    payload = json.loads(searched.stdout)
    result = payload["results"][0]
    assert result["citation"] == "[Algorithms, handout.pdf, Page 2]"
    assert result["extraction_status"] == "review-needed"
    assert "embedded-image" in result["extraction_reasons"]
    warning = next(
        item
        for item in payload["warnings"]
        if item["type"] == "extraction_review_needed"
    )
    assert warning["ordinal"] == "2"
    assert "embedded-image" in warning["reasons"]
    assert payload["sync_required"] is False


def test_vision_queue_and_store_scripts_round_trip(tmp_path: Path):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pdf_fixture(course / "handout.pdf")
    data_dir = tmp_path / "state"
    run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    queued = run_script(
        "vision_queue.py",
        "Algorithms",
        "--limit",
        "1",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    item = json.loads(queued.stdout)["items"][0]
    input_path = tmp_path / "descriptions.json"
    input_path.write_text(
        json.dumps(
            {
                "descriptions": [
                    {
                        "slide_id": item["slide_id"],
                        "description": "A weighted shortest-path graph diagram.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    stored = run_script(
        "store_visual_description.py",
        "--input",
        str(input_path),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    assert stored.returncode == 0, stored.stderr
    assert json.loads(stored.stdout)["stored"] == 1


def test_powerpoint_review_script_reports_layout_actions(tmp_path: Path):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pptx_fixture(
        course / "Lecture08.pptx",
        include_audit_slides=True,
    )
    data_dir = tmp_path / "state"
    indexed = run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    reviewed = run_script(
        "review_powerpoint.py",
        "Algorithms",
        "--reason",
        "chart-or-diagram",
        "--limit",
        "1",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    assert indexed.returncode == 0, indexed.stderr
    assert reviewed.returncode == 0, reviewed.stderr
    payload = json.loads(reviewed.stdout)
    assert payload["total_matches"] == 2
    assert payload["returned_items"] == 1
    assert payload["has_more"] is True
    assert payload["next_offset"] == 1
    assert payload["items"][0]["next_action"] == "export-to-pdf"


def test_script_errors_use_json_envelope(tmp_path: Path):
    result = run_script(
        "search_lectures.py",
        "anything",
        "--course",
        "Missing",
        "--limit",
        "0",
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["error"]["type"] == "ValueError"


def test_partial_sync_returns_failure_envelope_with_summary(tmp_path: Path):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pdf_fixture(course / "good.pdf")
    (course / "corrupt.pdf").write_bytes(b"not a pdf")

    result = run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["ok"] is False
    assert payload["error"]["type"] == "PartialSyncError"
    assert payload["indexed"] == 1
    assert payload["failed"] == 1
    assert len(payload["failures"]) == 1


def test_empty_search_tells_agent_to_synchronize(tmp_path: Path):
    result = run_script(
        "search_lectures.py",
        "memoization",
        "--course",
        "Algorithms",
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["results"] == []
    assert payload["sync_required"] is True
    assert "index_lectures.py" in payload["message"]


def test_indexed_no_match_suggests_alternative_terms_without_sync(
    tmp_path: Path,
):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pdf_fixture(course / "handout.pdf")
    data_dir = tmp_path / "state"
    run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    result = run_script(
        "search_lectures.py",
        "quaternion topology",
        "--course",
        "Algorithms",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["results"] == []
    assert payload["sync_required"] is False
    assert "alternative terms" in payload["message"]


def test_search_script_suggests_close_indexed_term_for_typo(tmp_path: Path):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pptx_fixture(course / "Lecture08.pptx")
    data_dir = tmp_path / "state"
    run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    result = run_script(
        "search_lectures.py",
        "memoiztion",
        "--course",
        "Algorithms",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["results"] == []
    assert "memoization" in payload["suggested_terms"]


def test_failed_refresh_requests_sync_and_marks_results_stale(tmp_path: Path):
    course = tmp_path / "Algorithms"
    course.mkdir()
    source = make_pdf_fixture(course / "handout.pdf")
    data_dir = tmp_path / "state"
    run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    source.write_bytes(b"not a pdf")
    failed_sync = run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    result = run_script(
        "search_lectures.py",
        "negative edges",
        "--course",
        "Algorithms",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert failed_sync.returncode == 1
    assert result.returncode == 0
    assert payload["sync_required"] is True
    assert payload["warnings"][0]["type"] == "source_failed"
    assert payload["results"][0]["source_status"] == "failed"
    assert payload["results"][0]["source_error"]


def test_ready_results_are_not_described_as_stale_when_other_source_failed(
    tmp_path: Path,
):
    course = tmp_path / "Algorithms"
    course.mkdir()
    good = make_pdf_fixture(course / "good.pdf")
    bad = make_pdf_fixture(course / "bad.pdf")
    data_dir = tmp_path / "state"
    run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    bad.write_bytes(b"not a pdf")
    run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    result = run_script(
        "search_lectures.py",
        "negative edges",
        "--course",
        "Algorithms",
        "--source",
        good.name,
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert payload["sync_required"] is True
    assert {item["source_status"] for item in payload["results"]} == {"ready"}
    assert "returned results are from ready sources" in payload["message"].lower()


def test_search_script_accepts_source_and_ordinal_filters(tmp_path: Path):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pdf_fixture(course / "handout.pdf")
    data_dir = tmp_path / "state"
    run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    result = run_script(
        "search_lectures.py",
        "negative edges",
        "--course",
        "Algorithms",
        "--source",
        "handout.pdf",
        "--ordinal",
        "2",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["results"][0]["source_file"] == "handout.pdf"
    assert payload["results"][0]["ordinal"] == 2


def test_read_script_returns_exhaustive_page_with_citations(tmp_path: Path):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pdf_fixture(course / "handout.pdf")
    data_dir = tmp_path / "state"
    run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    first = run_script(
        "read_lectures.py",
        "--course",
        "Algorithms",
        "--limit",
        "1",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    first_payload = json.loads(first.stdout)
    second = run_script(
        "read_lectures.py",
        "--course",
        "Algorithms",
        "--cursor",
        first_payload["next_cursor"],
        "--limit",
        "1",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    second_payload = json.loads(second.stdout)

    assert first.returncode == 0, first.stderr
    assert first_payload["total_records"] == 2
    assert first_payload["returned_records"] == 1
    assert first_payload["has_more"] is True
    assert first_payload["records"][0]["citation"] == (
        "[Algorithms, handout.pdf, Page 1]"
    )
    assert second.returncode == 0, second.stderr
    assert second_payload["records"][0]["ordinal"] == 2


def test_compact_search_omits_large_content_then_exact_read_restores_it(
    tmp_path: Path,
):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pdf_fixture(course / "handout.pdf")
    data_dir = tmp_path / "state"
    run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    full = run_script(
        "search_lectures.py",
        "precise-content",
        "--course",
        "Algorithms",
        "--limit",
        "1",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    compact = run_script(
        "search_lectures.py",
        "precise-content",
        "--course",
        "Algorithms",
        "--limit",
        "1",
        "--compact",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    exact = run_script(
        "read_lectures.py",
        "--course",
        "Algorithms",
        "--source",
        "handout.pdf",
        "--ordinal",
        "1",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    bounded = run_script(
        "read_record.py",
        "--course",
        "Algorithms",
        "--source",
        "handout.pdf",
        "--ordinal",
        "1",
        "--field",
        "raw_text",
        "--limit",
        "8000",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    full_payload = json.loads(full.stdout)
    compact_payload = json.loads(compact.stdout)
    exact_payload = json.loads(exact.stdout)
    bounded_payload = json.loads(bounded.stdout)
    compact_result = compact_payload["results"][0]
    assert len(full.stdout) > 100_000
    assert len(compact.stdout) < 5_000
    assert len(compact.stdout) < len(full.stdout) * 0.05
    assert compact_payload["compact"] is True
    assert compact_payload["omitted_content_chars"] > 100_000
    assert compact_result["citation"] == (
        "[Algorithms, handout.pdf, Page 1]"
    )
    assert "evidence" in compact_result
    assert "raw_text" not in compact_result
    assert "body_text" not in compact_result
    assert full_payload["results"][0]["raw_text"].count("precise-content") == (
        10_000
    )
    assert exact_payload["total_records"] == 1
    assert exact_payload["records"][0]["raw_text"].count("precise-content") == (
        10_000
    )
    assert bounded.returncode == 0, bounded.stderr
    assert len(bounded.stdout) < 10_000
    assert bounded_payload["returned_chars"] == 8_000
    assert bounded_payload["has_more"] is True
    assert bounded_payload["next_offset"] == 8_000


def test_read_script_validation_uses_json_error_envelope(tmp_path: Path):
    result = run_script(
        "read_lectures.py",
        "--course",
        "Algorithms",
        "--cursor",
        "broken",
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["error"]["type"] == "ValueError"


def test_semantic_search_explains_missing_optional_dependencies(tmp_path: Path):
    result = run_script(
        "search_lectures.py",
        "memoization",
        "--semantic",
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["error"]["type"] == "RuntimeError"
    assert ".[embeddings]" in payload["error"]["message"]


def test_hashing_embeddings_work_without_optional_dependencies(tmp_path: Path):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pptx_fixture(course / "Lecture08.pptx")
    data_dir = tmp_path / "state"
    run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    built = run_script(
        "build_embeddings.py",
        "Algorithms",
        "--backend",
        "hashing",
        "--dimensions",
        "128",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    searched = run_script(
        "search_lectures.py",
        "memoization subproblems",
        "--course",
        "Algorithms",
        "--semantic",
        "--backend",
        "hashing",
        "--dimensions",
        "128",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    built_payload = json.loads(built.stdout)
    search_payload = json.loads(searched.stdout)
    assert built.returncode == 0, built.stderr
    assert built_payload["backend"] == "hashing"
    assert built_payload["model"] == "hashing-v1:128"
    assert built_payload["embedded"] == 2
    assert searched.returncode == 0, searched.stderr
    assert search_payload["results"][0]["title"] == "Dynamic Programming"


def test_flashcard_conversion_script_preserves_citations_and_refuses_overwrite(
    tmp_path: Path,
):
    source = tmp_path / "cards.json"
    output = tmp_path / "cards.tsv"
    source.write_text(
        json.dumps(
            {
                "cards": [
                    {
                        "front": "What is memoization?",
                        "back": "Caching repeated subproblems.",
                        "citation": "[Algorithms, Lecture08.pptx, Slide 2]",
                        "tags": ["dynamic-programming"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    converted = run_script(
        "convert_flashcards.py",
        str(source),
        str(output),
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )
    refused = run_script(
        "convert_flashcards.py",
        str(source),
        str(output),
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    payload = json.loads(converted.stdout)
    refused_payload = json.loads(refused.stdout)
    assert converted.returncode == 0, converted.stderr
    assert payload["converted"] == 1
    assert "[Algorithms, Lecture08.pptx, Slide 2]" in output.read_text(
        encoding="utf-8"
    )
    assert refused.returncode == 1
    assert refused_payload["error"]["type"] == "FileExistsError"


@pytest.mark.parametrize(
    ("script", "arguments"),
    [
        ("index_lectures.py", ("--unknown", "--json")),
        ("search_lectures.py", ("--unknown", "--json")),
        ("read_lectures.py", ("--unknown", "--json")),
        ("read_record.py", ("--unknown", "--json")),
        ("build_embeddings.py", ("--unknown", "--json")),
        ("convert_flashcards.py", ("--unknown", "--json")),
        ("review_powerpoint.py", ("--unknown", "--json")),
        ("vision_queue.py", ("--unknown", "--json")),
        ("store_visual_description.py", ("--unknown", "--json")),
        ("remove_course.py", ("--unknown", "--json")),
        ("run_ocr.py", ("--unknown", "--json")),
    ],
)
def test_argument_errors_use_json_envelope(
    tmp_path: Path,
    script: str,
    arguments: tuple[str, ...],
):
    result = run_script(
        script,
        *arguments,
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert result.stderr == ""
    assert payload["ok"] is False
    assert payload["error"]["type"] == "ArgumentError"


def test_remove_course_script_requires_confirmation_and_preserves_source(
    tmp_path: Path,
):
    course = tmp_path / "Algorithms"
    course.mkdir()
    source = make_pdf_fixture(course / "handout.pdf")
    original = source.read_bytes()
    data_dir = tmp_path / "state"
    run_script(
        "index_lectures.py",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    refused = run_script(
        "remove_course.py",
        "Algorithms",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    removed = run_script(
        "remove_course.py",
        "Algorithms",
        "--confirm",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    assert refused.returncode == 1
    assert json.loads(refused.stdout)["ok"] is False
    assert removed.returncode == 0
    assert json.loads(removed.stdout)["removed"] is True
    assert source.read_bytes() == original
