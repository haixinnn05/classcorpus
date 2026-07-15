from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Protocol

from classcorpus.database import Database


@dataclass(frozen=True, slots=True)
class OCRResult:
    text: str
    confidence: float


@dataclass(frozen=True, slots=True)
class OCRQueueItem:
    slide_id: int
    course: str
    source_file: str
    ordinal: int
    image_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OCRStoredResult:
    slide_id: int
    source_file: str
    ordinal: int
    text: str
    confidence: float
    backend: str


@dataclass(frozen=True, slots=True)
class OCRRunReport:
    processed: int
    failed: int
    results: tuple[OCRStoredResult, ...]
    failures: tuple[dict[str, object], ...]


class OCRAdapter(Protocol):
    backend: str

    def recognize(self, image_paths: tuple[str, ...]) -> OCRResult: ...


class TesseractAdapter:
    def __init__(self, language: str = "eng"):
        try:
            import pytesseract
            from pytesseract import Output
        except ImportError as error:
            raise RuntimeError(
                'install the OCR adapter with: pip install -e ".[ocr]"'
            ) from error
        self.language = language
        self.backend = f"tesseract:{language}"
        self._pytesseract = pytesseract
        self._output_type = Output.DICT

    def recognize(self, image_paths: tuple[str, ...]) -> OCRResult:
        words: list[str] = []
        confidences: list[float] = []
        for image_path in image_paths:
            data = self._pytesseract.image_to_data(
                image_path,
                lang=self.language,
                output_type=self._output_type,
            )
            for text, raw_confidence in zip(
                data.get("text", []),
                data.get("conf", []),
                strict=False,
            ):
                word = str(text).strip()
                try:
                    confidence = float(raw_confidence)
                except (TypeError, ValueError):
                    continue
                if word and confidence >= 0:
                    words.append(word)
                    confidences.append(min(confidence, 100.0) / 100.0)
        return OCRResult(
            text=" ".join(words),
            confidence=(
                sum(confidences) / len(confidences) if confidences else 0.0
            ),
        )


def get_ocr_queue(
    database: Database,
    course: str,
    *,
    limit: int = 10,
    retry_failed: bool = False,
) -> list[OCRQueueItem]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    statuses = ("pending", "failed") if retry_failed else ("pending",)
    placeholders = ",".join("?" for _ in statuses)
    rows = database.connection.execute(
        f"""
        SELECT slides.id AS slide_id, courses.name AS course,
               source_files.relative_path AS source_file, slides.ordinal,
               slides.render_path
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE courses.name = ?
          AND slides.ocr_status IN ({placeholders})
        ORDER BY source_files.relative_path, slides.ordinal
        """,
        [course, *statuses],
    ).fetchall()
    items: list[OCRQueueItem] = []
    for row in rows:
        render_paths = (
            (str(row["render_path"]),)
            if row["render_path"] and Path(row["render_path"]).is_file()
            else ()
        )
        asset_paths = tuple(
            asset.path
            for asset in database.visual_assets_for_slide(int(row["slide_id"]))
            if Path(asset.path).is_file()
        )
        image_paths = render_paths or asset_paths
        if not image_paths:
            continue
        items.append(
            OCRQueueItem(
                slide_id=int(row["slide_id"]),
                course=str(row["course"]),
                source_file=str(row["source_file"]),
                ordinal=int(row["ordinal"]),
                image_paths=image_paths,
            )
        )
        if len(items) == limit:
            break
    return items


def process_ocr_queue(
    database: Database,
    course: str,
    adapter: OCRAdapter,
    *,
    limit: int = 10,
    retry_failed: bool = False,
) -> OCRRunReport:
    queue = get_ocr_queue(
        database,
        course,
        limit=limit,
        retry_failed=retry_failed,
    )
    stored: list[OCRStoredResult] = []
    failures: list[dict[str, object]] = []
    for item in queue:
        try:
            result = adapter.recognize(item.image_paths)
            _validate_result(result)
            _store_result(database, item.slide_id, adapter.backend, result)
        except Exception as error:
            with database.connection:
                database.connection.execute(
                    """
                    UPDATE slides
                    SET ocr_status = 'failed', ocr_backend = ?
                    WHERE id = ?
                    """,
                    (adapter.backend, item.slide_id),
                )
            failures.append(
                {
                    "slide_id": item.slide_id,
                    "source_file": item.source_file,
                    "ordinal": item.ordinal,
                    "type": type(error).__name__,
                    "message": str(error),
                }
            )
            continue
        stored.append(
            OCRStoredResult(
                slide_id=item.slide_id,
                source_file=item.source_file,
                ordinal=item.ordinal,
                text=result.text,
                confidence=result.confidence,
                backend=adapter.backend,
            )
        )
    return OCRRunReport(
        processed=len(stored),
        failed=len(failures),
        results=tuple(stored),
        failures=tuple(failures),
    )


def _validate_result(result: OCRResult) -> None:
    if not isinstance(result.text, str):
        raise ValueError("OCR text must be a string")
    if (
        not isinstance(result.confidence, (int, float))
        or isinstance(result.confidence, bool)
        or not math.isfinite(float(result.confidence))
        or not 0.0 <= float(result.confidence) <= 1.0
    ):
        raise ValueError("OCR confidence must be between 0 and 1")


def _store_result(
    database: Database,
    slide_id: int,
    backend: str,
    result: OCRResult,
) -> None:
    with database.connection:
        database.connection.execute(
            """
            UPDATE slides
            SET ocr_text = ?, ocr_confidence = ?,
                ocr_backend = ?, ocr_status = 'complete'
            WHERE id = ?
            """,
            (result.text, result.confidence, backend, slide_id),
        )
        database.connection.execute(
            "UPDATE slide_fts SET ocr_text = ? WHERE slide_id = ?",
            (result.text, slide_id),
        )
        database.connection.execute(
            "DELETE FROM slide_embeddings WHERE slide_id = ?",
            (slide_id,),
        )


__all__ = [
    "OCRAdapter",
    "OCRQueueItem",
    "OCRResult",
    "OCRRunReport",
    "OCRStoredResult",
    "TesseractAdapter",
    "get_ocr_queue",
    "process_ocr_queue",
]

