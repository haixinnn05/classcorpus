import json
import os
import subprocess
import sys
from pathlib import Path

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
    result = json.loads(searched.stdout)["results"][0]
    assert result["citation"] == "[Algorithms, handout.pdf, Page 2]"


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
