from pathlib import Path

import pytest

from classcorpus.database import Database
from classcorpus.embeddings import build_embeddings
from classcorpus.indexer import sync_course
from classcorpus.search import reciprocal_rank_fusion, search
from tests.fixtures.make_fixtures import make_pptx_fixture


class FakeEncoder:
    model_name = "fake-v1"

    def encode(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            normalized = text.lower()
            vectors.append(
                [1.0, 0.0]
                if "memoization" in normalized or "cached" in normalized
                else [0.0, 1.0]
            )
        return vectors


@pytest.fixture
def indexed_course(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "Algorithms"
    root.mkdir()
    make_pptx_fixture(root / "Lecture08.pptx")
    database = Database(tmp_path / "index.sqlite3")
    database.initialize()
    assert sync_course(database, "Algorithms", root).indexed == 1
    return database


def test_embeddings_are_optional(indexed_course: Database):
    results = search(indexed_course, "memoization", course="Algorithms")
    assert results[0].title == "Dynamic Programming"


def test_hybrid_search_uses_stored_vectors(indexed_course: Database):
    count = build_embeddings(indexed_course, "Algorithms", FakeEncoder())
    results = search(
        indexed_course,
        "cached recursion",
        course="Algorithms",
        encoder=FakeEncoder(),
    )

    assert count == 2
    assert results[0].title == "Dynamic Programming"


def test_hybrid_search_honors_source_and_ordinal_filters(indexed_course: Database):
    build_embeddings(indexed_course, "Algorithms", FakeEncoder())

    results = search(
        indexed_course,
        "cached recursion",
        course="Algorithms",
        source_file="Lecture08.pptx",
        ordinal=1,
        encoder=FakeEncoder(),
    )

    assert [(result.source_file, result.ordinal) for result in results] == [
        ("Lecture08.pptx", 1)
    ]
    assert search(
        indexed_course,
        "cached recursion",
        course="Algorithms",
        source_file="missing.pptx",
        encoder=FakeEncoder(),
    ) == []


def test_rank_fusion_rewards_results_in_both_rankings():
    scores = reciprocal_rank_fusion([[1, 2], [2, 3]])
    assert scores[2] > scores[1]
    assert scores[2] > scores[3]
