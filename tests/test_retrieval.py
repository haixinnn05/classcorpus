import json
from pathlib import Path

import pytest

from classcorpus.database import Database
from classcorpus.indexer import sync_course
from classcorpus.payloads import estimate_tokens
from classcorpus.retrieval import retrieve_focused


@pytest.fixture
def focused_course(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Database, Path]:
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "Physics"
    root.mkdir()
    target = root / "target.md"
    target.write_text(
        "# Motion focus-marker\n\n"
        "The unique answer is terminal velocity.\n\n"
        + ("Physics motion evidence and worked examples. " * 80),
        encoding="utf-8",
    )
    for index in range(1, 3):
        (root / f"alternative-{index}.md").write_text(
            f"# Physics motion alternative {index}\n\n"
            + ("Physics motion background and examples. " * 40),
            encoding="utf-8",
        )
    database = Database(tmp_path / "index.sqlite3")
    database.initialize()
    assert sync_course(database, "Physics", root).indexed == 3
    return database, target


def test_focused_retrieval_deduplicates_selected_passage(
    focused_course: tuple[Database, Path],
):
    database, _ = focused_course
    payload = retrieve_focused(
        database,
        "physics motion focus-marker",
        course="Physics",
    )

    selected = payload["selected"]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert selected["source_file"] == "target.md"
    assert selected["citation"] == "[Physics, target.md, Page 1]"
    assert selected["returned_chars"] == 1_200
    assert selected["next_offset"] == 1_200
    assert "terminal velocity" in selected["text"]
    assert len(payload["alternatives"]) == 2
    assert "snippet" not in serialized
    assert "source_path" not in serialized
    assert serialized.count("The unique answer is terminal velocity.") == 1
    assert payload["estimated_tokens"] == estimate_tokens(payload)


def test_focused_retrieval_cache_key_tracks_content(
    focused_course: tuple[Database, Path],
):
    database, target = focused_course
    arguments = {
        "query": "physics motion focus-marker",
        "course": "Physics",
    }
    first = retrieve_focused(database, **arguments)
    repeated = retrieve_focused(database, **arguments)
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            "terminal velocity",
            "updated terminal speed",
        ),
        encoding="utf-8",
    )
    assert sync_course(database, "Physics", target.parent).indexed == 1
    changed = retrieve_focused(database, **arguments)

    assert first["cache_key"] == repeated["cache_key"]
    assert changed["cache_key"] != first["cache_key"]


def test_focused_retrieval_no_match_is_actionable(
    focused_course: tuple[Database, Path],
):
    database, _ = focused_course
    payload = retrieve_focused(
        database,
        "quaternion topology",
        course="Physics",
    )

    assert payload["selected"] is None
    assert payload["alternatives"] == []
    assert payload["sync_required"] is False
    assert "alternative terms" in payload["message"]


@pytest.mark.parametrize("read_limit", [0, 50_001])
def test_focused_retrieval_rejects_invalid_read_limit(
    focused_course: tuple[Database, Path],
    read_limit: int,
):
    database, _ = focused_course
    with pytest.raises(ValueError, match="read_limit"):
        retrieve_focused(
            database,
            "unused",
            course="Physics",
            read_limit=read_limit,
        )
