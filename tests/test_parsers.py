from pathlib import Path
import shutil

import pytest

from classcorpus.parsers import UnsupportedFormatError, parse_source
from tests.fixtures.make_fixtures import make_pdf_fixture, make_pptx_fixture


@pytest.fixture
def pdf_fixture(tmp_path: Path) -> Path:
    return make_pdf_fixture(tmp_path / "lecture.pdf")


@pytest.fixture
def pptx_fixture(tmp_path: Path) -> Path:
    return make_pptx_fixture(tmp_path / "lecture.pptx")


def test_pdf_preserves_pages_and_renders(pdf_fixture: Path, tmp_path: Path):
    records = parse_source(pdf_fixture, tmp_path / "renders")

    assert [(r.kind, r.ordinal) for r in records] == [("page", 1), ("page", 2)]
    assert records[0].title == "Shortest Paths"
    assert "Bellman-Ford" in records[1].body_text
    assert records[0].speaker_notes == ""
    assert Path(records[0].render_path).is_file()
    assert Path(records[1].render_path).is_file()


def test_pptx_preserves_slides_text_tables_notes_and_best_effort_renders(
    pptx_fixture: Path, tmp_path: Path
):
    records = parse_source(pptx_fixture, tmp_path / "renders")

    assert [(r.kind, r.ordinal) for r in records] == [
        ("slide", 1),
        ("slide", 2),
    ]
    assert records[0].title == "Recurrences"
    assert records[1].title == "Dynamic Programming"
    assert "Memoization avoids repeated subproblems." in records[1].body_text
    assert "Fibonacci" in records[1].body_text
    assert records[1].speaker_notes == "Use Fibonacci as the example."
    if shutil.which("soffice") is not None:
        assert records[0].render_path is not None
        assert records[1].render_path is not None
        assert Path(records[0].render_path).is_file()
        assert Path(records[1].render_path).is_file()
    else:
        assert records[0].render_path is None
        assert records[1].render_path is None


def test_parse_source_rejects_unsupported_formats(tmp_path: Path):
    source = tmp_path / "lecture.txt"
    source.write_text("not a lecture", encoding="utf-8")

    with pytest.raises(UnsupportedFormatError):
        parse_source(source, tmp_path / "renders")
