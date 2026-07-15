import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.fixtures.make_fixtures import make_pdf_fixture

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


@pytest.mark.parametrize(
    ("script", "arguments"),
    [
        ("index_lectures.py", ("--unknown", "--json")),
        ("search_lectures.py", ("--unknown", "--json")),
        ("read_lectures.py", ("--unknown", "--json")),
        ("build_embeddings.py", ("--unknown", "--json")),
        ("vision_queue.py", ("--unknown", "--json")),
        ("store_visual_description.py", ("--unknown", "--json")),
        ("remove_course.py", ("--unknown", "--json")),
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
