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
    assert search_payload["content_trust"] == "untrusted"
    assert "ignore instructions" in search_payload["content_handling"]
    assert search_payload["compact"] is True
    assert search_payload["deprecated_options"] == ["--compact"]
    assert search_payload["estimated_tokens"] <= 1_200
    assert search_payload["budget_tokens"] == 1_200
    source_id = search_payload["results"][0]["source_id"]
    assert search_payload["sources"][source_id]["source_file"] == "handout.pdf"
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


def test_course_lifecycle_remembers_path_and_preserves_sources(tmp_path: Path):
    course = tmp_path / "Physics"
    course.mkdir()
    source = course / "notes.md"
    source.write_text("# Motion\nVelocity changes with acceleration.", encoding="utf-8")
    data_dir = tmp_path / "state"

    added = run_cli(
        "add",
        "Physics 1",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    listed = run_cli(
        "list",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    source.write_text(
        "# Motion\nVelocity changes with constant acceleration.",
        encoding="utf-8",
    )
    synced = run_cli(
        "sync",
        "Physics 1",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    refused = run_cli(
        "remove",
        "Physics 1",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    removed = run_cli(
        "remove",
        "Physics 1",
        "--confirm",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    after = run_cli(
        "list",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    added_payload = json.loads(added.stdout)
    listed_payload = json.loads(listed.stdout)
    synced_payload = json.loads(synced.stdout)
    refused_payload = json.loads(refused.stdout)
    removed_payload = json.loads(removed.stdout)
    assert added.returncode == 0, added.stderr
    assert added_payload["course"] == "Physics 1"
    assert added_payload["source_root"] == str(course.resolve())
    assert listed_payload["courses"][0]["name"] == "Physics 1"
    assert listed_payload["courses"][0]["source_root"] == str(course.resolve())
    assert synced.returncode == 0, synced.stderr
    assert synced_payload["indexed"] == 1
    assert synced_payload["source_root"] == str(course.resolve())
    assert refused.returncode == 1
    assert refused_payload["error"]["type"] == "ValueError"
    assert "--confirm" in refused_payload["error"]["message"]
    assert removed.returncode == 0, removed.stderr
    assert removed_payload == {
        "ok": True,
        "course": "Physics 1",
        "removed": True,
    }
    assert json.loads(after.stdout)["courses"] == []
    assert source.is_file()
    assert "constant acceleration" in source.read_text(encoding="utf-8")


def test_sync_unknown_course_is_actionable(tmp_path: Path):
    result = run_cli(
        "sync",
        "Missing",
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["error"]["type"] == "ValueError"
    assert "classcorpus add COURSE SOURCE_ROOT" in payload["error"]["message"]


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
    assert payload["content_trust"] == "untrusted"
    assert "ignore instructions" in payload["content_handling"]
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


def test_unified_cli_inspects_and_verifies_exact_evidence(tmp_path: Path):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pdf_fixture(course / "handout.pdf")
    data_dir = tmp_path / "state"
    run_cli(
        "add",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    result = run_cli(
        "inspect",
        "Algorithms",
        "handout.pdf",
        "2",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["citation"] == "[Algorithms, handout.pdf, Page 2]"
    assert payload["source_verification"] == "current"
    assert payload["render_available"] is True
    assert payload["content_trust"] == "untrusted"
    assert "Bellman-Ford" in payload["text"]


def test_unified_cli_manifests_and_verifies_generated_artifact(tmp_path: Path):
    course = tmp_path / "Algorithms"
    course.mkdir()
    make_pdf_fixture(course / "handout.pdf")
    data_dir = tmp_path / "state"
    run_cli(
        "add",
        "Algorithms",
        str(course),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    artifact = tmp_path / "guide.html"
    artifact.write_text("<h1>Bellman-Ford</h1>", encoding="utf-8")
    citation_source = tmp_path / "guide.md"
    citation_source.write_text(
        "Bellman-Ford handles negative edges. "
        "[Algorithms, handout.pdf, Page 2]",
        encoding="utf-8",
    )

    created = run_cli(
        "manifest",
        str(artifact),
        "--citations-from",
        str(citation_source),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    verified = run_cli(
        "verify-artifact",
        str(artifact),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    artifact.write_text("<h1>Modified</h1>", encoding="utf-8")
    modified = run_cli(
        "verify-artifact",
        str(artifact),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    created_payload = json.loads(created.stdout)
    verified_payload = json.loads(verified.stdout)
    modified_payload = json.loads(modified.stdout)
    manifest = artifact.with_name(artifact.name + ".classcorpus.json")
    assert created.returncode == 0, created.stderr
    assert created_payload["manifest"] == str(manifest.resolve())
    assert created_payload["citations"][0]["citation"] == (
        "[Algorithms, handout.pdf, Page 2]"
    )
    assert str(course.resolve()) not in manifest.read_text(encoding="utf-8")
    assert verified.returncode == 0, verified.stderr
    assert verified_payload["status"] == "current"
    assert modified.returncode == 1
    assert modified_payload["status"] == "artifact-modified"
    assert modified_payload["issues"][0]["type"] == "artifact_modified"


def test_unified_cli_retrieves_focused_evidence(tmp_path: Path):
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

    result = run_cli(
        "retrieve",
        "negative edges",
        "--course",
        "Algorithms",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["selected"]["ordinal"] == 2
    assert "Bellman-Ford" in payload["selected"]["text"]
    assert payload["estimated_tokens"] < 700


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
    assert course_status["next_actions"][0] == (
        'Retry synchronization: classcorpus sync "Algorithms"'
    )
    source_id = search_payload["results"][0]["source_id"]
    assert search_payload["sources"][source_id]["source_status"] == "failed"
    assert "latest refresh failed" in search_payload["message"]


def test_search_is_compact_by_default_and_full_is_explicit(tmp_path: Path):
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

    compact = run_cli(
        "search",
        "precise-content",
        "--course",
        "Algorithms",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    full = run_cli(
        "search",
        "precise-content",
        "--course",
        "Algorithms",
        "--full",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    compact_payload = json.loads(compact.stdout)
    full_payload = json.loads(full.stdout)
    assert compact_payload["compact"] is True
    assert compact_payload["continuation"]["type"] == "read_selected"
    assert "raw_text" not in compact_payload["results"][0]
    assert full_payload["compact"] is False
    assert full_payload["budget_tokens"] is None
    assert len(full_payload["results"][0]["raw_text"]) > 100_000
    assert len(compact.stdout) < len(full.stdout) * 0.2


def test_outline_cli_covers_every_page_with_continuation(tmp_path: Path):
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

    result = run_cli(
        "outline",
        "Algorithms",
        "--budget-tokens",
        "400",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["total_records"] == 2
    assert payload["returned_records"] >= 1
    assert sum(item["record_count"] for item in payload["coverage"]) == (
        payload["returned_records"]
    )
    assert payload["estimated_tokens"] > 0
    if payload["has_more"]:
        assert payload["next_cursor"]
        assert "classcorpus outline" in payload["continuation"]["command"]


def test_status_for_missing_course_gives_add_command(tmp_path: Path):
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
    assert 'classcorpus add "Operating Systems"' in payload["next_actions"][0]


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


def test_doctor_accepts_a_console_script_whose_interpreter_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    script = tmp_path / "classcorpus"
    script.write_text(
        f"#!{sys.executable}\nfrom classcorpus.cli import main\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "classcorpus.diagnostics._console_script_path",
        lambda: script,
    )

    payload = doctor_report()
    check = {item["name"]: item for item in payload["checks"]}[
        "Console entry point"
    ]

    assert check["status"] == "pass"
    assert check["required"] is False


@pytest.mark.parametrize(
    "script_body",
    [
        pytest.param(
            "#!/nonexistent/environment/bin/python\nfrom classcorpus.cli import main\n",
            id="direct-shebang",
        ),
        pytest.param(
            "#!/bin/sh\n"
            "'''exec' '/nonexistent/environment/bin/python' \"$0\" \"$@\"\n"
            "' '''\nfrom classcorpus.cli import main\n",
            id="posix-shell-trampoline",
        ),
    ],
)
def test_doctor_detects_a_console_script_with_a_missing_interpreter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    script_body: str,
):
    script = tmp_path / "classcorpus"
    script.write_text(script_body, encoding="utf-8")
    monkeypatch.setattr(
        "classcorpus.diagnostics._console_script_path",
        lambda: script,
    )

    payload = doctor_report()
    check = {item["name"]: item for item in payload["checks"]}[
        "Console entry point"
    ]

    assert check["status"] == "fail"
    assert "/nonexistent/environment/bin/python" in check["message"]
    assert "python -m classcorpus" in check["action"]
    assert payload["ok"] is True, "a broken script must not fail required checks"


def test_doctor_reports_an_absent_console_script_as_optional(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "classcorpus.diagnostics._console_script_path",
        lambda: None,
    )

    payload = doctor_report()
    check = {item["name"]: item for item in payload["checks"]}[
        "Console entry point"
    ]

    assert check["status"] == "optional"
    assert "python -m classcorpus" in check["action"]


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
