import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig

import pytest

from classcorpus.diagnostics import doctor_report
from tests.fixtures.make_fixtures import make_pdf_fixture, make_pptx_fixture

ROOT = Path(__file__).resolve().parents[1]


def run_cli(
    *arguments: str,
    data_dir: Path,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["CLASSCORPUS_DATA_DIR"] = str(data_dir)
    python_path = environment.get("PYTHONPATH")
    source_path = str(ROOT / "src")
    environment["PYTHONPATH"] = (
        f"{source_path}{os.pathsep}{python_path}" if python_path else source_path
    )
    return subprocess.run(
        [sys.executable, "-m", "classcorpus", *arguments],
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_unified_cli_indexes_searches_and_reports_course_status(tmp_path: Path):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pdf_fixture(course / "handout.pdf")
    data_dir = tmp_path / "state"
    unrelated = tmp_path / "elsewhere"
    unrelated.mkdir()

    indexed = run_cli(
        "index",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=unrelated,
    )
    searched = run_cli(
        "search",
        "negative edges",
        "--course",
        "Algorithms",
        "--compact",
        "--json",
        data_dir=data_dir,
        cwd=unrelated,
    )
    status = run_cli(
        "status",
        "--course",
        "Algorithms",
        "--json",
        data_dir=data_dir,
        cwd=unrelated,
    )

    index_payload = json.loads(indexed.stdout)
    search_payload = json.loads(searched.stdout)
    status_payload = json.loads(status.stdout)
    assert indexed.returncode == 0, indexed.stderr
    assert index_payload["indexed"] == 1
    assert searched.returncode == 0, searched.stderr
    assert search_payload["results"][0]["citation"] == (
        "[Algorithms, handout.pdf, Page 2]"
    )
    assert search_payload["compact"] is True
    assert "raw_text" not in search_payload["results"][0]
    assert status.returncode == 0, status.stderr
    assert status_payload["course_count"] == 1
    course_status = status_payload["courses"][0]
    assert course_status["sources_total"] == 1
    assert course_status["sources_ready"] == 1
    assert course_status["sources_failed"] == 0
    assert course_status["records_total"] == 2
    assert course_status["records_review_needed"] == 1
    assert course_status["ocr_pending"] == 2
    assert course_status["embedded_records"] == 0
    assert course_status["next_actions"]


def test_unified_cli_reads_bounded_record_chunks(tmp_path: Path):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pdf_fixture(course / "handout.pdf")
    data_dir = tmp_path / "state"
    run_cli(
        "index",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    first = run_cli(
        "read",
        "Algorithms",
        "handout.pdf",
        "1",
        "--field",
        "raw_text",
        "--limit",
        "80",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    human = run_cli(
        "read",
        "Algorithms",
        "handout.pdf",
        "2",
        "--limit",
        "20",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    payload = json.loads(first.stdout)
    assert first.returncode == 0, first.stderr
    assert payload["citation"] == "[Algorithms, handout.pdf, Page 1]"
    assert payload["field"] == "raw_text"
    assert payload["offset"] == 0
    assert payload["returned_chars"] == 80
    assert payload["has_more"] is True
    assert payload["next_offset"] == 80
    assert len(payload["text"]) == 80
    assert human.returncode == 0, human.stderr
    assert "[Algorithms, handout.pdf, Page 2]" in human.stdout
    assert "Continue: classcorpus read" in human.stdout
    assert "--offset 20" in human.stdout


def test_unified_cli_read_errors_use_json_envelope(tmp_path: Path):
    result = run_cli(
        "read",
        "Algorithms",
        "missing.pdf",
        "1",
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["error"]["type"] == "ValueError"
    assert "record not found" in payload["error"]["message"]


def test_status_identifies_failed_refresh_and_exact_retry_command(tmp_path: Path):
    course = tmp_path / "Algorithms"
    course.mkdir()
    source = make_pdf_fixture(course / "handout.pdf")
    data_dir = tmp_path / "state"
    run_cli(
        "index",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    source.write_bytes(b"not a pdf")

    failed = run_cli(
        "index",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    status = run_cli(
        "status",
        "--course",
        "Algorithms",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    searched = run_cli(
        "search",
        "negative edges",
        "--course",
        "Algorithms",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    failed_payload = json.loads(failed.stdout)
    course_status = json.loads(status.stdout)["courses"][0]
    search_payload = json.loads(searched.stdout)
    assert failed.returncode == 1
    assert failed_payload["error"]["type"] == "PartialSyncError"
    assert course_status["sources_failed"] == 1
    assert "classcorpus index" in course_status["next_actions"][0]
    assert str(course) in course_status["next_actions"][0]
    assert search_payload["results"][0]["source_status"] == "failed"
    assert "latest refresh failed" in search_payload["message"]


def test_status_for_missing_course_gives_index_command(tmp_path: Path):
    result = run_cli(
        "status",
        "--course",
        "Operating Systems",
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["courses"] == []
    assert 'classcorpus index "Operating Systems"' in payload["next_actions"][0]


def test_doctor_reports_core_and_optional_dependencies(tmp_path: Path):
    result = run_cli(
        "doctor",
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    required = [check for check in payload["checks"] if check["required"]]
    optional = [check for check in payload["checks"] if not check["required"]]
    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert {".pdf", ".pptx", ".md", ".txt"}.issubset(
        payload["supported_formats"]
    )
    assert required
    assert all(check["status"] == "pass" for check in required)
    assert optional
    assert all(check["status"] in {"pass", "optional"} for check in optional)


def test_unified_cli_argument_errors_use_json_envelope(tmp_path: Path):
    result = run_cli(
        "search",
        "query",
        "--limit",
        "0",
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["error"]["type"] == "ValueError"


def test_unified_cli_has_human_readable_status(tmp_path: Path):
    result = run_cli(
        "status",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "No matching indexed courses." in result.stdout
    assert "Next:" in result.stdout


def test_unified_cli_prints_typo_suggestion_for_human_search(tmp_path: Path):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pptx_fixture(course / "Lecture08.pptx")
    data_dir = tmp_path / "state"
    run_cli(
        "index",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    result = run_cli(
        "search",
        "memoiztion",
        "--course",
        "Algorithms",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "Did you mean: memoization" in result.stdout


def test_doctor_turns_unusable_data_path_into_failed_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    not_a_directory = tmp_path / "file"
    not_a_directory.write_text("occupied", encoding="utf-8")
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(not_a_directory))

    payload = doctor_report()
    checks = {check["name"]: check for check in payload["checks"]}

    assert payload["ok"] is False
    assert payload["data_root"] == "unavailable"
    assert checks["Data directory"]["status"] == "fail"
    assert checks["Database"]["status"] == "fail"


def test_installed_console_entry_point_runs_doctor(tmp_path: Path):
    executable_name = "classcorpus.exe" if os.name == "nt" else "classcorpus"
    executable = Path(sysconfig.get_path("scripts")) / executable_name
    environment = os.environ.copy()
    environment["CLASSCORPUS_DATA_DIR"] = str(tmp_path / "state")

    result = subprocess.run(
        [str(executable), "doctor", "--json"],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert executable.is_file()
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["ok"] is True
