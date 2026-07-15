from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal

from classcorpus.database import Database
from classcorpus.models import ExtractionStatus, VisualAsset

ReviewState = Literal[
    "full-render-available",
    "asset-review-available",
    "asset-reviewed-layout-unverified",
    "pdf-export-required",
]
NextAction = Literal["inspect-render", "inspect-assets", "export-to-pdf"]

LAYOUT_REASONS = frozenset(
    {
        "embedded-image",
        "chart-or-diagram",
        "equation-or-embedded-object",
        "unmapped-ooxml-text",
    }
)


@dataclass(frozen=True, slots=True)
class PowerPointReviewItem:
    slide_id: int
    course: str
    source_file: str
    source_path: str
    ordinal: int
    title: str
    extraction_status: ExtractionStatus
    extraction_reasons: tuple[str, ...]
    render_path: str | None
    assets: tuple[VisualAsset, ...]
    review_state: ReviewState
    next_action: NextAction
    citation: str


@dataclass(frozen=True, slots=True)
class PowerPointReviewReport:
    items: tuple[PowerPointReviewItem, ...]
    total_matches: int
    returned_items: int
    has_more: bool
    offset: int
    next_offset: int | None
    by_reason: dict[str, int]
    by_state: dict[str, int]


def list_powerpoint_reviews(
    database: Database,
    course: str,
    *,
    source_file: str | None = None,
    reason: str | None = None,
    include_reviewed: bool = True,
    limit: int = 50,
    offset: int = 0,
) -> PowerPointReviewReport:
    if not course.strip():
        raise ValueError("course must not be blank")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if offset < 0:
        raise ValueError("offset must not be negative")
    if reason is not None and reason not in LAYOUT_REASONS:
        choices = ", ".join(sorted(LAYOUT_REASONS))
        raise ValueError(f"reason must be one of: {choices}")

    parameters: list[object] = [course]
    filters = [
        "courses.name = ?",
        "LOWER(source_files.relative_path) LIKE '%.pptx'",
    ]
    if source_file is not None:
        filters.append("source_files.relative_path = ?")
        parameters.append(source_file)
    if not include_reviewed:
        filters.append("slides.extraction_status != 'visually-reviewed'")

    rows = database.connection.execute(
        f"""
        SELECT
            slides.id AS slide_id,
            courses.name AS course,
            source_files.relative_path AS source_file,
            source_files.source_path,
            slides.ordinal,
            slides.title,
            slides.extraction_status,
            slides.extraction_reasons,
            slides.render_path
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE {' AND '.join(filters)}
        ORDER BY source_files.relative_path, slides.ordinal
        """,
        parameters,
    ).fetchall()

    items: list[PowerPointReviewItem] = []
    for row in rows:
        reasons = tuple(json.loads(row["extraction_reasons"]))
        if not LAYOUT_REASONS.intersection(reasons):
            continue
        if reason is not None and reason not in reasons:
            continue
        items.append(_review_item(database, row, reasons))

    by_reason = Counter(
        item_reason
        for item in items
        for item_reason in item.extraction_reasons
        if item_reason in LAYOUT_REASONS
    )
    by_state = Counter(item.review_state for item in items)
    total_matches = len(items)
    page = tuple(items[offset : offset + limit])
    next_offset = offset + len(page)
    has_more = next_offset < total_matches
    return PowerPointReviewReport(
        items=page,
        total_matches=total_matches,
        returned_items=len(page),
        has_more=has_more,
        offset=offset,
        next_offset=next_offset if has_more else None,
        by_reason=dict(sorted(by_reason.items())),
        by_state=dict(sorted(by_state.items())),
    )


def _review_item(
    database: Database,
    row,
    reasons: tuple[str, ...],
) -> PowerPointReviewItem:
    render_path = (
        str(row["render_path"])
        if row["render_path"] and Path(row["render_path"]).is_file()
        else None
    )
    assets = tuple(
        asset
        for asset in database.visual_assets_for_slide(int(row["slide_id"]))
        if Path(asset.path).is_file()
    )
    status = str(row["extraction_status"])
    if render_path is not None:
        review_state: ReviewState = "full-render-available"
        next_action: NextAction = "inspect-render"
    elif assets and status != "visually-reviewed":
        review_state = "asset-review-available"
        next_action = "inspect-assets"
    elif assets:
        review_state = "asset-reviewed-layout-unverified"
        next_action = "export-to-pdf"
    else:
        review_state = "pdf-export-required"
        next_action = "export-to-pdf"

    return PowerPointReviewItem(
        slide_id=int(row["slide_id"]),
        course=str(row["course"]),
        source_file=str(row["source_file"]),
        source_path=str(row["source_path"]),
        ordinal=int(row["ordinal"]),
        title=str(row["title"]),
        extraction_status=row["extraction_status"],
        extraction_reasons=reasons,
        render_path=render_path,
        assets=assets,
        review_state=review_state,
        next_action=next_action,
        citation=(
            f"[{row['course']}, {row['source_file']}, Slide {row['ordinal']}]"
        ),
    )


__all__ = [
    "LAYOUT_REASONS",
    "PowerPointReviewItem",
    "PowerPointReviewReport",
    "list_powerpoint_reviews",
]

