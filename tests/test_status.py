from pathlib import Path

import pytest

from classcorpus.database import Database
from classcorpus.embeddings import build_embeddings
from classcorpus.encoders import HashingEncoder
from classcorpus.indexer import sync_course
from classcorpus.status import status_report
from tests.fixtures.make_fixtures import make_pptx_fixture


def test_status_reports_embedding_models_and_review_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "Algorithms"
    root.mkdir()
    make_pptx_fixture(
        root / "Lecture08.pptx",
        include_audit_slides=True,
    )
    database = Database(tmp_path / "index.sqlite3")
    database.initialize()
    sync_course(database, "Algorithms", root)
    build_embeddings(
        database,
        "Algorithms",
        HashingEncoder(dimensions=64),
    )

    report = status_report(database, course="Algorithms")
    status = report["courses"][0]

    assert status["records_total"] == 6
    assert status["records_review_needed"] == 5
    assert status["embedded_records"] == 6
    assert status["embedding_models"] == ("hashing-v1:64",)
    assert status["next_actions"] == (
        "Review extraction-risk records before relying on complete visual "
        "coverage.",
    )
