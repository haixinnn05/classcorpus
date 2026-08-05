from pathlib import Path

import pytest

from classcorpus.database import Database
from classcorpus.indexer import sync_course
from classcorpus.inspection import inspect_record
from tests.fixtures.make_fixtures import make_pdf_fixture


@pytest.fixture
def inspected_course(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Database, Path]:
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "Algorithms"
    root.mkdir()
    source = make_pdf_fixture(root / "handout.pdf")
    database = Database(tmp_path / "index.sqlite3")
    database.initialize()
    assert sync_course(database, "Algorithms", root).indexed == 1
    return database, source


def test_inspect_returns_exact_evidence_preview_and_current_hash(
    inspected_course: tuple[Database, Path],
):
    database, source = inspected_course
    payload = inspect_record(
        database,
        course="Algorithms",
        source_file="handout.pdf",
        ordinal=2,
    )

    assert payload["citation"] == "[Algorithms, handout.pdf, Page 2]"
    assert payload["source_path"] == str(source.resolve())
    assert payload["source_verification"] == "current"
    assert payload["current_sha256"] == payload["indexed_sha256"]
    assert payload["current_parser_version"] == payload["indexed_parser_version"]
    assert payload["render_available"] is True
    assert Path(payload["render_path"]).is_file()
    assert payload["content_trust"] == "untrusted"
    assert "Bellman-Ford" in payload["text"]
    assert any(
        warning["type"] == "extraction_review_needed" for warning in payload["warnings"]
    )


def test_inspect_warns_when_source_changed_or_disappeared(
    inspected_course: tuple[Database, Path],
):
    database, source = inspected_course
    source.write_bytes(b"changed after indexing")

    changed = inspect_record(
        database,
        course="Algorithms",
        source_file="handout.pdf",
        ordinal=1,
    )
    source.unlink()
    missing = inspect_record(
        database,
        course="Algorithms",
        source_file="handout.pdf",
        ordinal=1,
    )

    assert changed["source_verification"] == "changed"
    assert changed["current_sha256"] != changed["indexed_sha256"]
    assert changed["warnings"][0]["type"] == "source_changed"
    assert missing["source_verification"] == "missing"
    assert missing["current_sha256"] is None
    assert missing["warnings"][0]["type"] == "source_missing"


def test_inspect_detects_stale_parser_and_builds_continuation(
    inspected_course: tuple[Database, Path],
):
    database, _ = inspected_course
    with database.connection:
        database.connection.execute("UPDATE source_files SET parser_version = 'old'")

    payload = inspect_record(
        database,
        course="Algorithms",
        source_file="handout.pdf",
        ordinal=1,
        field="raw_text",
        limit=80,
    )

    assert payload["source_verification"] == "stale-parser"
    assert payload["warnings"][0]["type"] == "source_stale_parser"
    assert payload["next_offset"] == 80
    assert payload["continuation"]["next_offset"] == 80
    assert "classcorpus inspect" in payload["continuation"]["command"]
    assert "--offset 80" in payload["continuation"]["command"]
