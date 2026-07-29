import json
from pathlib import Path

import pytest

from classcorpus.claims import check_claims
from classcorpus.database import Database
from classcorpus.indexer import sync_course

LECTURE = """# Shortest Paths

Bellman-Ford relaxes every edge V - 1 times. The running time is O(V * E),
which is slower than Dijkstra. One extra relaxation pass detects a negative
cycle. Dijkstra requires non-negative edge weights because it never revisits a
settled vertex.
"""


@pytest.fixture
def course(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "state"))
    lectures = tmp_path / "Algorithms"
    lectures.mkdir()
    (lectures / "paths.md").write_text(LECTURE, encoding="utf-8")
    database = Database()
    database.initialize()
    sync_course(database, "Algorithms", lectures)
    return database


def write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "guide.md"
    path.write_text(body, encoding="utf-8")
    return path


def test_a_true_claim_is_supported(course: Database, tmp_path: Path):
    source = write(
        tmp_path,
        "Bellman-Ford relaxes every edge V - 1 times "
        "[Algorithms, paths.md, Page 1].\n",
    )

    payload = check_claims(course, source)

    assert payload["ok"] is True
    assert payload["claims_total"] == 1
    assert payload["claims"][0]["verdict"] == "supported"
    assert payload["claims"][0]["support"] == 1.0


def test_a_fabricated_complexity_is_unsupported(course: Database, tmp_path: Path):
    """The citation is well formed and the record exists; only the value is wrong."""
    source = write(
        tmp_path,
        "Bellman-Ford runs in O(V log V) time [Algorithms, paths.md, Page 1].\n",
    )

    payload = check_claims(course, source)
    claim = payload["claims"][0]

    assert payload["ok"] is False
    assert claim["verdict"] == "unsupported"
    assert "O(V log V)" in claim["missing_measurements"]


def test_whitespace_in_a_complexity_does_not_cause_a_false_alarm(
    course: Database,
    tmp_path: Path,
):
    """`O(V*E)` and `O(V * E)` are the same claim."""
    source = write(
        tmp_path,
        "The running time is O(V*E) [Algorithms, paths.md, Page 1].\n",
    )

    payload = check_claims(course, source)

    assert payload["claims"][0]["missing_measurements"] == []
    assert payload["claims"][0]["verdict"] == "supported"


def test_an_invented_number_is_unsupported(course: Database, tmp_path: Path):
    source = write(
        tmp_path,
        "Bellman-Ford needs 7 relaxation passes [Algorithms, paths.md, Page 1].\n",
    )

    payload = check_claims(course, source)

    assert payload["claims"][0]["verdict"] == "unsupported"
    assert "7" in payload["claims"][0]["missing_measurements"]


def test_unrelated_wording_is_flagged_as_weak(course: Database, tmp_path: Path):
    source = write(
        tmp_path,
        "Quantum entanglement accelerates traversal "
        "[Algorithms, paths.md, Page 1].\n",
    )

    payload = check_claims(course, source)

    assert payload["claims"][0]["verdict"] == "weak"
    assert payload["claims"][0]["support"] < 0.6


def test_a_missing_record_is_unverified(course: Database, tmp_path: Path):
    source = write(
        tmp_path,
        "A claim about nothing [Algorithms, absent.md, Page 4].\n",
    )

    payload = check_claims(course, source)

    assert payload["ok"] is False
    assert payload["claims"][0]["verdict"] == "unverified"
    assert "not indexed" in payload["claims"][0]["message"]


def test_each_citation_in_a_paragraph_is_checked_separately(
    course: Database,
    tmp_path: Path,
):
    source = write(
        tmp_path,
        "The running time is O(V * E) [Algorithms, paths.md, Page 1]. "
        "It also runs in O(V log V) [Algorithms, paths.md, Page 1].\n",
    )

    payload = check_claims(course, source)
    verdicts = [claim["verdict"] for claim in payload["claims"]]

    assert payload["claims_total"] == 2
    assert verdicts == ["supported", "unsupported"]


def test_list_items_and_line_numbers_are_reported(course: Database, tmp_path: Path):
    source = write(
        tmp_path,
        "# Guide\n\n"
        "- Dijkstra requires non-negative weights "
        "[Algorithms, paths.md, Page 1]\n",
    )

    payload = check_claims(course, source)
    claim = payload["claims"][0]

    assert claim["line"] == 3
    assert claim["claim"].startswith("Dijkstra requires")
    assert claim["verdict"] == "supported"


def test_a_document_without_citations_is_reported_not_crashed(
    course: Database,
    tmp_path: Path,
):
    source = write(tmp_path, "# Guide\n\nProse with no citations at all.\n")

    payload = check_claims(course, source)

    assert payload["ok"] is True
    assert payload["claims_total"] == 0
    assert "No citations found" in payload["message"]


def test_payload_marks_source_derived_content_as_untrusted(
    course: Database,
    tmp_path: Path,
):
    source = write(
        tmp_path,
        "A claim [Algorithms, paths.md, Page 1].\n",
    )

    payload = check_claims(course, source)

    assert payload["content_trust"] == "untrusted"
    assert "not proof of entailment" in payload["method"]


def test_threshold_is_validated(course: Database, tmp_path: Path):
    source = write(tmp_path, "A claim [Algorithms, paths.md, Page 1].\n")

    with pytest.raises(ValueError, match="threshold"):
        check_claims(course, source, threshold=0)
    with pytest.raises(ValueError, match="threshold"):
        check_claims(course, source, threshold=1.5)


def test_a_missing_source_file_is_an_error(course: Database, tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        check_claims(course, tmp_path / "absent.md")


def test_unknown_field_is_rejected(course: Database, tmp_path: Path):
    source = write(tmp_path, "A claim [Algorithms, paths.md, Page 1].\n")

    with pytest.raises(ValueError, match="unknown field"):
        check_claims(course, source, field="nonsense")


def test_json_payload_is_serializable(course: Database, tmp_path: Path):
    source = write(
        tmp_path,
        "Bellman-Ford runs in O(V log V) [Algorithms, paths.md, Page 1].\n",
    )

    payload = check_claims(course, source)

    assert json.loads(json.dumps(payload))["counts"]["unsupported"] == 1


def run_cli(*arguments: str, data_dir: Path, cwd: Path):
    import os
    import subprocess
    import sys

    environment = os.environ.copy()
    environment["CLASSCORPUS_DATA_DIR"] = str(data_dir)
    source_path = str(Path(__file__).resolve().parents[1] / "src")
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{source_path}{os.pathsep}{existing}" if existing else source_path
    )
    return subprocess.run(
        [sys.executable, "-m", "classcorpus", *arguments],
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_exits_nonzero_on_an_unsupported_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    data_dir = tmp_path / "state"
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(data_dir))
    lectures = tmp_path / "Algorithms"
    lectures.mkdir()
    (lectures / "paths.md").write_text(LECTURE, encoding="utf-8")
    database = Database()
    database.initialize()
    sync_course(database, "Algorithms", lectures)
    source = write(
        tmp_path,
        "Bellman-Ford runs in O(V log V) [Algorithms, paths.md, Page 1].\n",
    )

    result = run_cli(
        "check-claims", str(source), "--json", data_dir=data_dir, cwd=tmp_path
    )
    human = run_cli("check-claims", str(source), data_dir=data_dir, cwd=tmp_path)

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["counts"]["unsupported"] == 1
    assert human.returncode == 1
    assert "UNSUPPORTED" in human.stdout
    assert "O(V log V)" in human.stdout
