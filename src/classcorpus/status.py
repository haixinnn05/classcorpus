from __future__ import annotations

from dataclasses import asdict, dataclass

from classcorpus.database import Database
from classcorpus.paths import data_root, database_path


@dataclass(frozen=True, slots=True)
class CourseStatus:
    name: str
    source_root: str
    sources_total: int
    sources_ready: int
    sources_failed: int
    records_total: int
    records_review_needed: int
    records_visually_reviewed: int
    ocr_pending: int
    ocr_complete: int
    ocr_failed: int
    embedded_records: int
    embedding_models: tuple[str, ...]
    next_actions: tuple[str, ...]


def status_report(
    database: Database,
    *,
    course: str | None = None,
) -> dict[str, object]:
    parameters: list[object] = []
    where = ""
    if course is not None:
        where = "WHERE courses.name = ?"
        parameters.append(course)
    course_rows = database.connection.execute(
        f"""
        SELECT courses.id, courses.name, courses.source_root
        FROM courses
        {where}
        ORDER BY courses.name
        """,
        parameters,
    ).fetchall()
    statuses = tuple(_course_status(database, row) for row in course_rows)
    actions: list[str] = []
    if course is not None and not statuses:
        actions.append(
            f'Index the course with: classcorpus index "{course}" SOURCE_ROOT'
        )
    elif not statuses:
        actions.append(
            'Index a course with: classcorpus index "COURSE" SOURCE_ROOT'
        )
    return {
        "ok": True,
        "data_root": str(data_root()),
        "database_path": str(database_path()),
        "course_count": len(statuses),
        "courses": [asdict(status) for status in statuses],
        "next_actions": actions,
    }


def _course_status(database: Database, course_row) -> CourseStatus:
    course_id = int(course_row["id"])
    source_counts = database.connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(status = 'ready'), 0) AS ready,
            COALESCE(SUM(status = 'failed'), 0) AS failed
        FROM source_files
        WHERE course_id = ?
        """,
        (course_id,),
    ).fetchone()
    record_counts = database.connection.execute(
        """
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(slides.extraction_status = 'review-needed'), 0)
                AS review_needed,
            COALESCE(SUM(slides.extraction_status = 'visually-reviewed'), 0)
                AS visually_reviewed,
            COALESCE(SUM(slides.ocr_status = 'pending'), 0) AS ocr_pending,
            COALESCE(SUM(slides.ocr_status = 'complete'), 0) AS ocr_complete,
            COALESCE(SUM(slides.ocr_status = 'failed'), 0) AS ocr_failed
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        WHERE source_files.course_id = ?
        """,
        (course_id,),
    ).fetchone()
    embedding_rows = database.connection.execute(
        """
        SELECT DISTINCT slide_embeddings.model_name
        FROM slide_embeddings
        JOIN slides ON slides.id = slide_embeddings.slide_id
        JOIN source_files ON source_files.id = slides.source_file_id
        WHERE source_files.course_id = ?
        ORDER BY slide_embeddings.model_name
        """,
        (course_id,),
    ).fetchall()
    embedded_records = database.connection.execute(
        """
        SELECT COUNT(DISTINCT slide_embeddings.slide_id)
        FROM slide_embeddings
        JOIN slides ON slides.id = slide_embeddings.slide_id
        JOIN source_files ON source_files.id = slides.source_file_id
        WHERE source_files.course_id = ?
        """,
        (course_id,),
    ).fetchone()[0]
    actions: list[str] = []
    name = str(course_row["name"])
    source_root = str(course_row["source_root"])
    if int(source_counts["failed"]):
        actions.append(
            f'Retry synchronization: classcorpus index "{name}" "{source_root}"'
        )
    if int(record_counts["review_needed"]):
        actions.append(
            "Review extraction-risk records before relying on complete visual "
            "coverage."
        )
    if int(record_counts["ocr_failed"]):
        actions.append(
            "Fix the local OCR dependency or image error, then retry failed OCR."
        )
    return CourseStatus(
        name=name,
        source_root=source_root,
        sources_total=int(source_counts["total"]),
        sources_ready=int(source_counts["ready"]),
        sources_failed=int(source_counts["failed"]),
        records_total=int(record_counts["total"]),
        records_review_needed=int(record_counts["review_needed"]),
        records_visually_reviewed=int(record_counts["visually_reviewed"]),
        ocr_pending=int(record_counts["ocr_pending"]),
        ocr_complete=int(record_counts["ocr_complete"]),
        ocr_failed=int(record_counts["ocr_failed"]),
        embedded_records=int(embedded_records),
        embedding_models=tuple(
            str(row["model_name"]) for row in embedding_rows
        ),
        next_actions=tuple(actions),
    )


__all__ = ["CourseStatus", "status_report"]

