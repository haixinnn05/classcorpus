from pathlib import Path

import pytest

from classcorpus.database import Database
from classcorpus.indexer import sync_course
from classcorpus.search import search
from classcorpus.vision import get_vision_queue, store_descriptions
from tests.fixtures.make_fixtures import make_pdf_fixture


@pytest.fixture
def indexed_course(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "Algorithms"
    root.mkdir()
    make_pdf_fixture(root / "handout.pdf")
    database = Database(tmp_path / "index.sqlite3")
    database.initialize()
    assert sync_course(database, "Algorithms", root).indexed == 1
    return database


def test_queue_only_returns_rendered_pending_slides(indexed_course: Database):
    items = get_vision_queue(indexed_course, "Algorithms", limit=10)

    assert len(items) == 2
    assert all(Path(item.render_path).is_file() for item in items)
    assert [item.ordinal for item in items] == [1, 2]


def test_storing_description_removes_item_and_updates_search(
    indexed_course: Database,
):
    item = get_vision_queue(indexed_course, "Algorithms", limit=1)[0]
    count = store_descriptions(
        indexed_course,
        [
            {
                "slide_id": item.slide_id,
                "description": "A red-black tree rotation diagram.",
            }
        ],
    )

    assert count == 1
    assert item.slide_id not in {
        queued.slide_id
        for queued in get_vision_queue(indexed_course, "Algorithms", limit=20)
    }
    assert search(indexed_course, "red black rotation")[0].slide_id == item.slide_id


def test_invalid_description_keeps_item_queued(indexed_course: Database):
    item = get_vision_queue(indexed_course, "Algorithms", limit=1)[0]

    with pytest.raises(ValueError, match="at least 10 characters"):
        store_descriptions(
            indexed_course,
            [{"slide_id": item.slide_id, "description": "short"}],
        )

    assert get_vision_queue(indexed_course, "Algorithms", limit=1)[0] == item
