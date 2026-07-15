from pathlib import Path

import pytest

from classcorpus.database import Database
from classcorpus.indexer import sync_course
from classcorpus.review import list_powerpoint_reviews
from classcorpus.vision import store_descriptions
from tests.fixtures.make_fixtures import make_pptx_fixture


@pytest.fixture
def reviewed_course(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "Algorithms"
    root.mkdir()
    make_pptx_fixture(root / "Lecture08.pptx", include_audit_slides=True)
    database = Database(tmp_path / "index.sqlite3")
    database.initialize()
    assert sync_course(database, "Algorithms", root).indexed == 1
    return database


def test_report_classifies_reviewability_and_next_actions(
    reviewed_course: Database,
):
    report = list_powerpoint_reviews(reviewed_course, "Algorithms")

    assert report.total_matches == 5
    assert report.returned_items == 5
    assert report.has_more is False
    assert report.by_reason == {
        "chart-or-diagram": 2,
        "embedded-image": 1,
        "equation-or-embedded-object": 2,
        "unmapped-ooxml-text": 1,
    }
    assert report.by_state == {
        "asset-review-available": 1,
        "pdf-export-required": 4,
    }
    picture = report.items[0]
    assert picture.ordinal == 1
    assert picture.review_state == "asset-review-available"
    assert picture.next_action == "inspect-assets"
    assert len(picture.assets) == 3
    assert picture.citation == "[Algorithms, Lecture08.pptx, Slide 1]"
    assert all(
        item.next_action == "export-to-pdf" for item in report.items[1:]
    )


def test_report_filters_reasons_and_paginates_without_hiding_total(
    reviewed_course: Database,
):
    chart_report = list_powerpoint_reviews(
        reviewed_course,
        "Algorithms",
        reason="chart-or-diagram",
        limit=1,
    )

    assert chart_report.total_matches == 2
    assert chart_report.returned_items == 1
    assert chart_report.has_more is True
    assert chart_report.next_offset == 1
    assert chart_report.items[0].ordinal == 3

    second_page = list_powerpoint_reviews(
        reviewed_course,
        "Algorithms",
        reason="chart-or-diagram",
        limit=1,
        offset=chart_report.next_offset,
    )
    assert second_page.items[0].ordinal == 5
    assert second_page.has_more is False
    assert second_page.next_offset is None


def test_asset_review_keeps_layout_limitation_visible(reviewed_course: Database):
    item = list_powerpoint_reviews(reviewed_course, "Algorithms").items[0]
    store_descriptions(
        reviewed_course,
        [
            {
                "slide_id": item.slide_id,
                "description": "Three repeated gray image assets.",
            }
        ],
    )

    reviewed = list_powerpoint_reviews(reviewed_course, "Algorithms").items[0]
    unreviewed = list_powerpoint_reviews(
        reviewed_course,
        "Algorithms",
        include_reviewed=False,
    )

    assert reviewed.review_state == "asset-reviewed-layout-unverified"
    assert reviewed.next_action == "export-to-pdf"
    assert reviewed.extraction_status == "visually-reviewed"
    assert reviewed.slide_id not in {item.slide_id for item in unreviewed.items}


@pytest.mark.parametrize(
    ("limit", "offset", "message"),
    [
        (0, 0, "limit must be at least 1"),
        (1, -1, "offset must not be negative"),
    ],
)
def test_report_rejects_invalid_pagination(
    reviewed_course: Database,
    limit: int,
    offset: int,
    message: str,
):
    with pytest.raises(ValueError, match=message):
        list_powerpoint_reviews(
            reviewed_course,
            "Algorithms",
            limit=limit,
            offset=offset,
        )
