from pathlib import Path

import pytest

from classcorpus.database import Database
from classcorpus.models import SlideRecord, SourceFingerprint, VisualAsset
from classcorpus.records import read_records


def _database_with_two_sources(tmp_path: Path) -> Database:
    database = Database(tmp_path / "classcorpus.sqlite3")
    database.initialize()
    course = database.upsert_course("Algorithms", tmp_path / "lectures")
    asset_path = tmp_path / "asset.png"
    asset_path.write_bytes(b"exact-asset")
    fingerprint = SourceFingerprint(1, 2, "abc", "3")
    database.replace_source(
        course.id,
        "b-slides.pptx",
        tmp_path / "lectures" / "b-slides.pptx",
        fingerprint,
        [
            SlideRecord(
                ordinal=1,
                kind="slide",
                title="B one",
                body_text="Body B1",
                speaker_notes="Note B1",
                raw_text="B one\n\nBody B1\nNote B1",
                extraction_status="review-needed",
                extraction_reasons=("chart",),
                native_text_chars=23,
                has_visual_content=True,
                visual_assets=(
                    VisualAsset(
                        path=str(asset_path),
                        kind="image",
                        shape_name="Picture 1",
                        content_type="image/png",
                        left=10,
                        top=20,
                        width=30,
                        height=40,
                    ),
                ),
            ),
            SlideRecord(
                ordinal=2,
                kind="slide",
                title="B two",
                body_text="Body B2",
                speaker_notes="",
                raw_text="B two\nBody B2",
                extraction_status="text-extracted",
                native_text_chars=13,
            ),
        ],
    )
    database.replace_source(
        course.id,
        "a-handout.pdf",
        tmp_path / "lectures" / "a-handout.pdf",
        fingerprint,
        [
            SlideRecord(
                ordinal=1,
                kind="page",
                title="A one",
                body_text="Body A1",
                speaker_notes="",
                raw_text="A one\n  exact spacing\n" + ("x" * 1000),
                extraction_status="text-extracted",
                native_text_chars=1022,
            ),
            SlideRecord(
                ordinal=2,
                kind="page",
                title="A two",
                body_text="Body A2",
                speaker_notes="",
                raw_text="A two\nBody A2",
                extraction_status="text-extracted",
                native_text_chars=13,
            ),
        ],
    )
    return database


def test_read_records_paginates_every_record_once_in_source_order(tmp_path: Path):
    database = _database_with_two_sources(tmp_path)
    records = []
    cursor = None

    while True:
        page = read_records(
            database,
            course="Algorithms",
            cursor=cursor,
            limit=2,
        )
        records.extend(page.records)
        if not page.has_more:
            break
        assert page.next_cursor
        cursor = page.next_cursor

    assert [(record.source_file, record.ordinal) for record in records] == [
        ("a-handout.pdf", 1),
        ("a-handout.pdf", 2),
        ("b-slides.pptx", 1),
        ("b-slides.pptx", 2),
    ]
    assert len({(record.source_file, record.ordinal) for record in records}) == 4
    assert page.total_records == 4
    assert sum(record.native_text_chars for record in records) == 1071


def test_read_records_returns_complete_evidence_and_scope_metadata(tmp_path: Path):
    database = _database_with_two_sources(tmp_path)

    page = read_records(database, course="Algorithms", limit=3)

    assert page.total_records == 4
    assert page.returned_records == 3
    assert page.has_more is True
    assert page.review_needed == 1
    assert page.warnings[0]["type"] == "extraction_review_needed"
    assert page.records[0].raw_text.endswith("x" * 1000)
    reviewed = page.records[2]
    assert reviewed.source_status == "ready"
    assert reviewed.source_error is None
    assert reviewed.extraction_reasons == ("chart",)
    assert reviewed.citation == "[Algorithms, b-slides.pptx, Slide 1]"
    assert reviewed.visual_assets[0].shape_name == "Picture 1"
    assert reviewed.visual_assets[0].width == 30


def test_read_records_source_filter_has_independent_totals(tmp_path: Path):
    database = _database_with_two_sources(tmp_path)

    page = read_records(
        database,
        course="Algorithms",
        source_file="b-slides.pptx",
        limit=20,
    )

    assert page.total_records == 2
    assert page.returned_records == 2
    assert page.review_needed == 1
    assert {record.source_file for record in page.records} == {"b-slides.pptx"}


def test_read_records_exact_ordinal_returns_one_complete_record(tmp_path: Path):
    database = _database_with_two_sources(tmp_path)

    page = read_records(
        database,
        course="Algorithms",
        source_file="a-handout.pdf",
        ordinal=1,
    )

    assert page.total_records == 1
    assert page.returned_records == 1
    assert page.has_more is False
    assert page.next_cursor is None
    assert page.records[0].raw_text.endswith("x" * 1000)


def test_read_records_rejects_cursor_with_exact_ordinal(tmp_path: Path):
    database = _database_with_two_sources(tmp_path)

    with pytest.raises(ValueError, match="cursor cannot be used with ordinal"):
        read_records(
            database,
            course="Algorithms",
            ordinal=1,
            cursor="unused",
        )


@pytest.mark.parametrize("cursor", ["not-base64!", "e30=", "W10="])
def test_read_records_rejects_malformed_cursor(tmp_path: Path, cursor: str):
    database = _database_with_two_sources(tmp_path)

    with pytest.raises(ValueError, match="cursor"):
        read_records(database, course="Algorithms", cursor=cursor)


def test_read_records_requires_positive_limit(tmp_path: Path):
    database = _database_with_two_sources(tmp_path)

    with pytest.raises(ValueError, match="limit"):
        read_records(database, course="Algorithms", limit=0)


def test_read_records_requires_positive_ordinal(tmp_path: Path):
    database = _database_with_two_sources(tmp_path)

    with pytest.raises(ValueError, match="ordinal"):
        read_records(database, course="Algorithms", ordinal=0)
