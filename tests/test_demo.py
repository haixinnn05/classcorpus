import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from classcorpus.demo import (
    DEMO_MARKER_NAME,
    demo_source_root,
    generate_demo_corpus,
)

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


def test_demo_generates_indexes_and_returns_cited_evidence(tmp_path: Path):
    data_dir = tmp_path / "state"

    result = run_cli("demo", "--json", data_dir=data_dir, cwd=tmp_path)

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert payload["ok"] is True
    assert payload["sync"]["failed"] == 0
    assert payload["sync"]["records_indexed"] >= 8
    assert payload["generated_files"] == [
        "Lecture01-Complexity.pptx",
        "handout-shortest-paths.pdf",
        "study-notes.md",
    ]

    results = payload["search"]["results"]
    assert results, "the demo must return at least one match for its own query"
    for item in results:
        assert item["citation"].startswith(f"[{payload['course']}, ")
        assert item["evidence"]


def test_demo_indexes_every_generated_format(tmp_path: Path):
    data_dir = tmp_path / "state"
    run_cli("demo", "--json", data_dir=data_dir, cwd=tmp_path)

    outline = run_cli(
        "outline",
        "ClassCorpus Demo",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    payload = json.loads(outline.stdout)
    indexed_files = {source["source_file"] for source in payload["sources"].values()}
    assert indexed_files == {
        "Lecture01-Complexity.pptx",
        "handout-shortest-paths.pdf",
        "study-notes.md",
    }
    assert payload["total_records"] >= len(indexed_files)


def test_demo_writes_into_generated_data_by_default(tmp_path: Path):
    data_dir = tmp_path / "state"

    result = run_cli("demo", "--json", data_dir=data_dir, cwd=tmp_path)

    payload = json.loads(result.stdout)
    source_root = Path(payload["source_root"])
    assert source_root.is_relative_to(data_dir.resolve())
    assert (source_root / DEMO_MARKER_NAME).is_file()


def test_demo_is_repeatable(tmp_path: Path):
    data_dir = tmp_path / "state"

    first = run_cli("demo", "--json", data_dir=data_dir, cwd=tmp_path)
    second = run_cli("demo", "--json", data_dir=data_dir, cwd=tmp_path)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout)["sync"]["failed"] == 0


def test_demo_accepts_an_explicit_empty_directory(tmp_path: Path):
    target = tmp_path / "demo-here"

    result = run_cli(
        "demo",
        "--dir",
        str(target),
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert Path(payload["source_root"]) == target.resolve()


def test_demo_refuses_to_write_into_an_unrelated_non_empty_directory(
    tmp_path: Path,
):
    lectures = tmp_path / "MyRealLectures"
    lectures.mkdir()
    original = lectures / "week-one.md"
    original.write_text("my own notes", encoding="utf-8")

    result = run_cli(
        "demo",
        "--dir",
        str(lectures),
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["error"]["type"] == "ValueError"
    assert "refusing to write" in payload["error"]["message"]
    assert original.read_text(encoding="utf-8") == "my own notes"
    assert list(lectures.iterdir()) == [original]


def test_demo_overwrite_is_explicit(tmp_path: Path):
    target = tmp_path / "scratch"
    target.mkdir()
    (target / "unrelated.md").write_text("placeholder", encoding="utf-8")

    result = run_cli(
        "demo",
        "--dir",
        str(target),
        "--overwrite",
        "--json",
        data_dir=tmp_path / "state",
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert (target / "handout-shortest-paths.pdf").is_file()


def test_demo_human_output_shows_citations_and_next_steps(tmp_path: Path):
    result = run_cli("demo", data_dir=tmp_path / "state", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert "[ClassCorpus Demo, " in result.stdout
    assert "classcorpus outline" in result.stdout


def test_generate_demo_corpus_reruns_over_its_own_output(tmp_path: Path):
    directory = tmp_path / "corpus"

    first = generate_demo_corpus(directory)
    second = generate_demo_corpus(directory)

    assert first == second
    for name in first:
        assert (directory / name).is_file()


def test_generate_demo_corpus_protects_unrelated_files(tmp_path: Path):
    directory = tmp_path / "corpus"
    directory.mkdir()
    (directory / "keep.pdf").write_bytes(b"not mine to touch")

    with pytest.raises(ValueError, match="refusing to write"):
        generate_demo_corpus(directory)

    assert (directory / "keep.pdf").read_bytes() == b"not mine to touch"


def test_demo_source_root_follows_the_data_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "state"))

    assert demo_source_root().is_relative_to(tmp_path / "state")
