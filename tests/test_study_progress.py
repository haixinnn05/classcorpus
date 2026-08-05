import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from classcorpus.database import Database
from classcorpus.flashcards import Flashcard, export_flashcards
from classcorpus.indexer import sync_course
from classcorpus.study_progress import (
    RATING_AGAIN,
    RATING_EASY,
    RATING_GOOD,
    deck_progress,
    export_progress,
    identify_card_content,
    identify_cards,
    import_progress,
    record_review,
)

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def progress_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Database, list[Flashcard], Path]:
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "state"))
    root = tmp_path / "Physics"
    root.mkdir()
    source = root / "motion.md"
    source.write_text(
        "# Motion\n\nVelocity changes when acceleration is nonzero.",
        encoding="utf-8",
    )
    database = Database()
    database.initialize()
    sync_course(database, "Physics", root)
    cards = [
        Flashcard(
            "When does velocity change?",
            "When acceleration is nonzero.",
            "[Physics, motion.md, Page 1]",
            ("kinematics",),
        ),
        Flashcard(
            "What quantity describes location?",
            "Position.",
            "[Physics, motion.md, Page 1]",
        ),
    ]
    return database, cards, source


def test_card_identity_is_stable_across_tags_but_tracks_source_version(
    progress_fixture: tuple[Database, list[Flashcard], Path],
):
    database, cards, source = progress_fixture
    first = identify_cards(database, cards)[0]
    retagged = Flashcard(
        cards[0].front,
        cards[0].back,
        cards[0].citation,
        ("exam-1",),
    )

    same_content = identify_cards(database, [retagged])[0]
    source.write_text("# Motion\n\nUpdated source.", encoding="utf-8")
    sync_course(database, "Physics", source.parent)
    updated = identify_cards(database, cards)[0]

    assert same_content.card_key == first.card_key
    assert same_content.card_id == first.card_id
    assert updated.card_key == first.card_key
    assert updated.card_id != first.card_id
    assert updated.source_sha256 != first.source_sha256


def test_content_identity_is_available_without_an_indexed_database():
    card = Flashcard("Question", "Answer", "[Course, notes.md, Page 1]")

    identity = identify_card_content(card)

    assert len(identity.card_key) == 24
    assert len(identity.card_id) == 24
    assert identity.source_sha256 == ""


def test_review_schedule_persists_good_easy_and_again_ratings(
    progress_fixture: tuple[Database, list[Flashcard], Path],
):
    database, cards, _ = progress_fixture
    card_id = identify_cards(database, cards)[0].card_id

    first = record_review(
        database,
        cards,
        card_id=card_id,
        rating=RATING_GOOD,
        confidence=4,
        reviewed_at=NOW,
    )
    second = record_review(
        database,
        cards,
        card_id=card_id,
        rating=RATING_EASY,
        confidence=5,
        reviewed_at=NOW + timedelta(days=1),
    )
    reset = record_review(
        database,
        cards,
        card_id=card_id,
        rating=RATING_AGAIN,
        confidence=1,
        reviewed_at=NOW + timedelta(days=8),
    )

    assert first["repetitions"] == 1
    assert first["interval_days"] == 1.0
    assert first["due_at"] == "2026-08-05T12:00:00+00:00"
    assert second["repetitions"] == 2
    assert second["interval_days"] == 7.0
    assert second["ease"] > first["ease"]
    assert reset["repetitions"] == 0
    assert reset["lapses"] == 1
    assert reset["interval_days"] == pytest.approx(10 / 1440)
    assert reset["due_at"] == "2026-08-12T12:10:00+00:00"


def test_progress_distinguishes_new_future_due_and_stale_cards(
    progress_fixture: tuple[Database, list[Flashcard], Path],
):
    database, cards, source = progress_fixture
    first_id = identify_cards(database, cards)[0].card_id
    record_review(
        database,
        cards,
        card_id=first_id,
        rating=RATING_GOOD,
        reviewed_at=NOW,
    )

    current = deck_progress(database, cards, now=NOW)
    due = deck_progress(database, cards, now=NOW + timedelta(days=2))
    source.write_text("# Motion\n\nThe lecture was replaced.", encoding="utf-8")
    sync_course(database, "Physics", source.parent)
    stale = deck_progress(database, cards, now=NOW + timedelta(days=2))

    assert current["summary"] == {
        "cards": 2,
        "new": 1,
        "due": 0,
        "future": 1,
        "stale": 0,
    }
    assert due["summary"]["due"] == 1
    assert stale["summary"]["stale"] == 1
    stale_card = next(card for card in stale["cards"] if card["status"] == "stale")
    assert stale_card["previous_card_id"] == first_id


def test_progress_export_and_import_round_trip_without_card_text(
    progress_fixture: tuple[Database, list[Flashcard], Path],
    tmp_path: Path,
):
    database, cards, _ = progress_fixture
    card_id = identify_cards(database, cards)[0].card_id
    record_review(
        database,
        cards,
        card_id=card_id,
        rating=RATING_GOOD,
        confidence=3,
        reviewed_at=NOW,
    )
    output = tmp_path / "progress.json"

    exported = export_progress(database, cards, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    restored_database = Database(tmp_path / "restored.sqlite3")
    restored_database.initialize()
    imported = import_progress(restored_database, output)

    assert exported["reviews"] == 1
    assert exported["events"] == 1
    assert "front" not in output.read_text(encoding="utf-8")
    assert "back" not in output.read_text(encoding="utf-8")
    assert payload["format"] == "classcorpus-study-progress"
    assert imported == {"ok": True, "reviews": 1, "events": 1}
    row = restored_database.connection.execute(
        "SELECT repetitions, interval_days FROM flashcard_reviews"
    ).fetchone()
    assert dict(row) == {"repetitions": 1, "interval_days": 1.0}


def test_progress_export_refuses_implicit_overwrite(
    progress_fixture: tuple[Database, list[Flashcard], Path],
    tmp_path: Path,
):
    database, cards, _ = progress_fixture
    output = tmp_path / "progress.json"
    output.write_text("owned", encoding="utf-8")

    with pytest.raises(FileExistsError, match="--overwrite"):
        export_progress(database, cards, output)

    assert output.read_text(encoding="utf-8") == "owned"


def _run_cli(*arguments: str, data_dir: Path, cwd: Path):
    environment = os.environ.copy()
    environment["CLASSCORPUS_DATA_DIR"] = str(data_dir)
    root = Path(__file__).resolve().parents[1]
    environment["PYTHONPATH"] = str(root / "src")
    return subprocess.run(
        [sys.executable, "-m", "classcorpus", *arguments],
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def test_review_cli_lists_rates_and_exports_progress(
    progress_fixture: tuple[Database, list[Flashcard], Path],
    tmp_path: Path,
):
    database, cards, _ = progress_fixture
    deck = tmp_path / "cards.json"
    export_flashcards(cards, deck)
    data_dir = Path(os.environ["CLASSCORPUS_DATA_DIR"])

    listed = _run_cli("review", str(deck), "--json", data_dir=data_dir, cwd=tmp_path)
    listed_payload = json.loads(listed.stdout)
    card_id = listed_payload["cards"][0]["card_id"]
    rated = _run_cli(
        "review",
        str(deck),
        "--card",
        card_id,
        "--rating",
        "good",
        "--confidence",
        "4",
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )
    progress_path = tmp_path / "progress.json"
    exported = _run_cli(
        "review",
        str(deck),
        "--export-progress",
        str(progress_path),
        "--json",
        data_dir=data_dir,
        cwd=tmp_path,
    )

    assert listed.returncode == 0, listed.stderr
    assert listed_payload["summary"]["new"] == 2
    assert rated.returncode == 0, rated.stderr
    assert json.loads(rated.stdout)["confidence"] == 4
    assert exported.returncode == 0, exported.stderr
    assert json.loads(exported.stdout)["reviews"] == 1
    assert progress_path.is_file()
    assert (
        database.connection.execute(
            "SELECT COUNT(*) FROM flashcard_reviews"
        ).fetchone()[0]
        == 1
    )
