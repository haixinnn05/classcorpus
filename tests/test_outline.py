from pathlib import Path

import pytest

from classcorpus.database import Database
from classcorpus.models import SlideRecord, SourceFingerprint
from classcorpus.outline import outline_course


def _outlined_database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "classcorpus.sqlite3")
    database.initialize()
    course = database.upsert_course("Physics", tmp_path / "lectures")
    fingerprint = SourceFingerprint(1, 2, "abc", "3")
    database.replace_source(
        course.id,
        "lecture.pdf",
        tmp_path / "lectures" / "lecture.pdf",
        fingerprint,
        [
            SlideRecord(
                ordinal=1,
                kind="page",
                title="Motion",
                body_text="x" * 4_000,
                speaker_notes="",
                raw_text="x" * 4_000,
                extraction_status="text-extracted",
                native_text_chars=4_000,
            ),
            SlideRecord(
                ordinal=2,
                kind="page",
                title="  MOTION  ",
                body_text="y" * 4_000,
                speaker_notes="",
                raw_text="y" * 4_000,
                extraction_status="review-needed",
                extraction_reasons=("embedded-image",),
                native_text_chars=4_000,
            ),
            SlideRecord(
                ordinal=3,
                kind="page",
                title="Forces " + ("and applications " * 20),
                body_text="z" * 4_000,
                speaker_notes="",
                raw_text="z" * 4_000,
                extraction_status="text-extracted",
                native_text_chars=4_000,
            ),
            SlideRecord(
                ordinal=4,
                kind="page",
                title="Energy " + ("and conservation " * 20),
                body_text="w" * 4_000,
                speaker_notes="",
                raw_text="w" * 4_000,
                extraction_status="text-extracted",
                native_text_chars=4_000,
            ),
        ],
    )
    return database


def test_outline_groups_matching_consecutive_titles(tmp_path: Path):
    payload = outline_course(
        _outlined_database(tmp_path),
        course="Physics",
        budget_tokens=10_000,
    )

    assert [
        (group["start_ordinal"], group["end_ordinal"])
        for group in payload["coverage"]
    ] == [(1, 2), (3, 3), (4, 4)]
    assert payload["coverage"][0]["record_count"] == 2
    assert payload["coverage"][0]["review_needed"] == 1
    assert payload["coverage"][0]["citation_start"].endswith("Page 1]")
    assert payload["coverage"][0]["citation_end"].endswith("Page 2]")


def test_outline_cursor_covers_every_record_once(tmp_path: Path):
    database = _outlined_database(tmp_path)
    cursor = None
    represented: list[int] = []

    while True:
        payload = outline_course(
            database,
            course="Physics",
            cursor=cursor,
            budget_tokens=500,
        )
        for group in payload["coverage"]:
            represented.extend(
                range(group["start_ordinal"], group["end_ordinal"] + 1)
            )
        if not payload["has_more"]:
            break
        assert payload["budget_exhausted"] is True
        assert payload["next_cursor"]
        cursor = payload["next_cursor"]

    assert represented == [1, 2, 3, 4]
    assert payload["remaining_records"] == 0


def test_outline_is_more_than_sixty_percent_smaller_than_full_records(
    tmp_path: Path,
):
    database = _outlined_database(tmp_path)
    outline = outline_course(
        database,
        course="Physics",
        budget_tokens=10_000,
    )
    full_rows = database.connection.execute(
        "SELECT raw_text, body_text, title FROM slides ORDER BY ordinal"
    ).fetchall()
    full_size = sum(
        len(row["raw_text"]) + len(row["body_text"]) + len(row["title"])
        for row in full_rows
    )

    assert len(str(outline)) < full_size * 0.4
    assert sum(item["record_count"] for item in outline["coverage"]) == 4


@pytest.mark.parametrize("cursor", ["broken!", "e30="])
def test_outline_rejects_malformed_cursor(tmp_path: Path, cursor: str):
    with pytest.raises(ValueError, match="cursor"):
        outline_course(
            _outlined_database(tmp_path),
            course="Physics",
            cursor=cursor,
        )


def test_outline_rejects_cursor_from_another_scope(tmp_path: Path):
    database = _outlined_database(tmp_path)
    cursor = outline_course(
        database,
        course="Physics",
        budget_tokens=500,
    )["next_cursor"]

    with pytest.raises(ValueError, match="cursor"):
        outline_course(
            database,
            course="Other",
            cursor=cursor,
        )
