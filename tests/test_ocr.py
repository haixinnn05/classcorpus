from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from classcorpus.database import Database
from classcorpus.embeddings import build_embeddings
from classcorpus.indexer import sync_course
from classcorpus.ocr import (
    OCRResult,
    TesseractAdapter,
    get_ocr_queue,
    process_ocr_queue,
)
from classcorpus.records import read_records
from classcorpus.search import search
from tests.fixtures.make_fixtures import make_pdf_fixture


class FakeEncoder:
    model_name = "fake-ocr-invalidation"

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, float(index + 1)] for index, _ in enumerate(texts)]


class FakeOCRAdapter:
    backend = "fake-ocr:v1"

    def recognize(self, image_paths: tuple[str, ...]) -> OCRResult:
        ordinal = int(Path(image_paths[0]).stem.rsplit("-", 1)[-1])
        return OCRResult(
            text=f"ocr-exclusive-term page {ordinal}",
            confidence=0.75 + ordinal / 100,
        )


@pytest.fixture
def ocr_course(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Database:
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "Algorithms"
    root.mkdir()
    make_pdf_fixture(root / "handout.pdf")
    database = Database(tmp_path / "index.sqlite3")
    database.initialize()
    assert sync_course(database, "Algorithms", root).indexed == 1
    return database


def test_ocr_queue_processes_local_images_and_exposes_confidence(
    ocr_course: Database,
):
    queue = get_ocr_queue(ocr_course, "Algorithms")
    report = process_ocr_queue(
        ocr_course,
        "Algorithms",
        FakeOCRAdapter(),
    )
    rows = ocr_course.connection.execute(
        """
        SELECT ocr_text, ocr_confidence, ocr_backend, ocr_status
        FROM slides ORDER BY ordinal
        """
    ).fetchall()

    assert len(queue) == 2
    assert report.processed == 2
    assert report.failed == 0
    assert [row["ocr_confidence"] for row in rows] == [0.76, 0.77]
    assert {row["ocr_backend"] for row in rows} == {"fake-ocr:v1"}
    assert {row["ocr_status"] for row in rows} == {"complete"}
    assert get_ocr_queue(ocr_course, "Algorithms") == []

    result = search(
        ocr_course,
        "ocr-exclusive-term",
        course="Algorithms",
        ordinal=2,
    )[0]
    assert result.ocr_text == "ocr-exclusive-term page 2"
    assert result.ocr_confidence == 0.77
    assert result.ocr_backend == "fake-ocr:v1"
    assert result.ocr_status == "complete"
    record = read_records(
        ocr_course,
        course="Algorithms",
        source_file="handout.pdf",
    ).records[1]
    assert record.ocr_text == "ocr-exclusive-term page 2"
    assert record.ocr_confidence == 0.77


def test_ocr_updates_invalidate_stale_embeddings(ocr_course: Database):
    build_embeddings(ocr_course, "Algorithms", FakeEncoder())
    before = ocr_course.connection.execute(
        "SELECT COUNT(*) FROM slide_embeddings"
    ).fetchone()[0]

    report = process_ocr_queue(
        ocr_course,
        "Algorithms",
        FakeOCRAdapter(),
        limit=1,
    )
    after = ocr_course.connection.execute(
        "SELECT COUNT(*) FROM slide_embeddings"
    ).fetchone()[0]

    assert before == 2
    assert report.processed == 1
    assert after == 1


def test_invalid_ocr_confidence_marks_record_failed_and_can_retry(
    ocr_course: Database,
):
    class InvalidAdapter:
        backend = "invalid"

        def recognize(self, image_paths: tuple[str, ...]) -> OCRResult:
            return OCRResult(text="bad confidence", confidence=1.5)

    failed = process_ocr_queue(
        ocr_course,
        "Algorithms",
        InvalidAdapter(),
        limit=1,
    )
    pending_only = get_ocr_queue(ocr_course, "Algorithms", limit=10)
    retryable = get_ocr_queue(
        ocr_course,
        "Algorithms",
        limit=10,
        retry_failed=True,
    )

    assert failed.processed == 0
    assert failed.failed == 1
    assert len(pending_only) == 1
    assert len(retryable) == 2


def test_initialize_migrates_existing_fts_and_preserves_search(
    ocr_course: Database,
):
    with ocr_course.connection:
        ocr_course.connection.execute("DROP TABLE slide_fts")
        ocr_course.connection.execute(
            """
            CREATE VIRTUAL TABLE slide_fts USING fts5(
                slide_id UNINDEXED, title, body_text,
                speaker_notes, visual_description
            )
            """
        )
        ocr_course.connection.execute(
            """
            INSERT INTO slide_fts(
                slide_id, title, body_text, speaker_notes, visual_description
            )
            SELECT id, title, body_text, speaker_notes,
                   COALESCE(visual_description, '')
            FROM slides
            """
        )

    ocr_course.initialize()
    columns = {
        row["name"]
        for row in ocr_course.connection.execute("PRAGMA table_info(slide_fts)")
    }

    assert "ocr_text" in columns
    assert search(ocr_course, "negative edges", course="Algorithms")


def test_tesseract_adapter_reports_mean_word_confidence(
    monkeypatch: pytest.MonkeyPatch,
):
    class Output:
        DICT = "dict"

    fake_pytesseract = SimpleNamespace(
        image_to_data=lambda *args, **kwargs: {
            "text": ["Alpha", "", "Beta"],
            "conf": ["80", "-1", "60"],
        }
    )
    monkeypatch.setitem(sys.modules, "pytesseract", fake_pytesseract)
    fake_pytesseract.Output = Output

    adapter = TesseractAdapter(language="eng")
    result = adapter.recognize(("/tmp/page.png",))

    assert adapter.backend == "tesseract:eng"
    assert result.text == "Alpha Beta"
    assert result.confidence == pytest.approx(0.7)


def test_tesseract_dependency_error_names_install_extra(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setitem(sys.modules, "pytesseract", None)

    with pytest.raises(RuntimeError, match=r"\.\[ocr\]"):
        TesseractAdapter()
