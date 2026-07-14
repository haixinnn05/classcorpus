from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping, Sequence

from classcorpus.database import Database


@dataclass(frozen=True, slots=True)
class VisionItem:
    slide_id: int
    course: str
    source_file: str
    source_path: str
    ordinal: int
    kind: Literal["slide", "page"]
    title: str
    render_path: str


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
            slides.render_path
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE courses.name = ?
          AND slides.render_path IS NOT NULL
          AND COALESCE(slides.visual_description, '') = ''
        ORDER BY source_files.relative_path, slides.ordinal
        """,
        (course,),
    ).fetchall()
    items: list[VisionItem] = []
    for row in rows:
        if not Path(row["render_path"]).is_file():
            continue
        items.append(VisionItem(**dict(row)))
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

    with database.connection:
        for slide_id, description in prepared:
            database.connection.execute(
                """
                UPDATE slides
                SET visual_description = ?, vision_status = 'complete'
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
