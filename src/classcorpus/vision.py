from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal, Mapping, Sequence

from classcorpus.database import Database
from classcorpus.models import ExtractionStatus, VisualAsset


@dataclass(frozen=True, slots=True)
class VisionItem:
    slide_id: int
    course: str
    source_file: str
    source_path: str
    ordinal: int
    kind: Literal["slide", "page"]
    title: str
    render_path: str | None
    extraction_status: ExtractionStatus
    extraction_reasons: tuple[str, ...]
    assets: tuple[VisualAsset, ...]
    asset_paths: tuple[str, ...]
    warning: dict[str, str] | None


def get_vision_queue(
    database: Database,
    course: str,
    *,
    limit: int = 10,
) -> list[VisionItem]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    rows = database.connection.execute(
        """
        SELECT
            slides.id AS slide_id,
            courses.name AS course,
            source_files.relative_path AS source_file,
            source_files.source_path,
            slides.ordinal,
            slides.kind,
            slides.title,
            slides.render_path,
            slides.extraction_status,
            slides.extraction_reasons
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE courses.name = ?
          AND COALESCE(slides.visual_description, '') = ''
          AND (
              slides.render_path IS NOT NULL
              OR slides.has_visual_content = 1
              OR slides.extraction_status = 'review-needed'
          )
        ORDER BY
            CASE slides.extraction_status
                WHEN 'review-needed' THEN 0
                ELSE 1
            END,
            source_files.relative_path,
            slides.ordinal
        """,
        (course,),
    ).fetchall()
    items: list[VisionItem] = []
    for row in rows:
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
        warning = None
        if render_path is None and not assets:
            warning = {
                "type": "visual-source-unavailable",
                "message": (
                    "No viewable render or embedded asset is available. "
                    "Export the lecture to PDF for visual review."
                ),
            }
        items.append(
            VisionItem(
                slide_id=int(row["slide_id"]),
                course=str(row["course"]),
                source_file=str(row["source_file"]),
                source_path=str(row["source_path"]),
                ordinal=int(row["ordinal"]),
                kind=row["kind"],
                title=str(row["title"]),
                render_path=render_path,
                extraction_status=row["extraction_status"],
                extraction_reasons=tuple(
                    json.loads(row["extraction_reasons"])
                ),
                assets=assets,
                asset_paths=tuple(asset.path for asset in assets),
                warning=warning,
            )
        )
        if len(items) == limit:
            break
    return items


def store_descriptions(
    database: Database,
    descriptions: Sequence[Mapping[str, object]],
) -> int:
    prepared: list[tuple[int, str]] = []
    seen: set[int] = set()
    for item in descriptions:
        try:
            slide_id = int(item["slide_id"])
            description = str(item["description"]).strip()
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                "each description requires integer slide_id and text description"
            ) from error
        if slide_id in seen:
            raise ValueError(f"duplicate slide_id: {slide_id}")
        if len(description) < 10:
            raise ValueError("description must be at least 10 characters")
        seen.add(slide_id)
        prepared.append((slide_id, description))

    if not prepared:
        return 0
    placeholders = ",".join("?" for _ in prepared)
    existing = {
        int(row["id"])
        for row in database.connection.execute(
            f"SELECT id FROM slides WHERE id IN ({placeholders})",
            [slide_id for slide_id, _ in prepared],
        )
    }
    missing = seen - existing
    if missing:
        raise ValueError(f"unknown slide_id: {min(missing)}")

    for slide_id, _ in prepared:
        row = database.connection.execute(
            "SELECT render_path FROM slides WHERE id = ?",
            (slide_id,),
        ).fetchone()
        render_exists = bool(
            row["render_path"] and Path(row["render_path"]).is_file()
        )
        asset_exists = any(
            Path(asset.path).is_file()
            for asset in database.visual_assets_for_slide(slide_id)
        )
        if not render_exists and not asset_exists:
            raise ValueError(
                f"slide_id {slide_id} has no viewable render or asset"
            )

    with database.connection:
        for slide_id, description in prepared:
            database.connection.execute(
                """
                UPDATE slides
                SET visual_description = ?,
                    vision_status = 'complete',
                    extraction_status = 'visually-reviewed'
                WHERE id = ?
                """,
                (description, slide_id),
            )
            database.connection.execute(
                """
                UPDATE slide_fts
                SET visual_description = ?
                WHERE slide_id = ?
                """,
                (description, slide_id),
            )
            database.connection.execute(
                "DELETE FROM slide_embeddings WHERE slide_id = ?",
                (slide_id,),
            )
    return len(prepared)


__all__ = ["VisionItem", "get_vision_queue", "store_descriptions"]
