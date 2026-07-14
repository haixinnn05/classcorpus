from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import fitz
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from classcorpus.models import SlideRecord


class UnsupportedFormatError(ValueError):
    def __init__(self, suffix: str):
        label = suffix or "<no extension>"
        super().__init__(f"Unsupported source format: {label}")


def parse_source(path: Path, render_dir: Path) -> list[SlideRecord]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(path, render_dir)
    if suffix == ".pptx":
        return _parse_pptx(path, render_dir)
    raise UnsupportedFormatError(suffix)


def _parse_pdf(path: Path, render_dir: Path) -> list[SlideRecord]:
    render_dir.mkdir(parents=True, exist_ok=True)

    records: list[SlideRecord] = []
    with fitz.open(path) as document:
        for ordinal, page in enumerate(document, start=1):
            page_text = _normalized_text(page.get_text("text"))
            title, body_text = _split_title_and_body(page_text)

            image_path = render_dir / f"page-{ordinal:04d}.png"
            page.get_pixmap(
                matrix=fitz.Matrix(1.5, 1.5),
                alpha=False,
            ).save(image_path)

            records.append(
                SlideRecord(
                    ordinal=ordinal,
                    kind="page",
                    title=title,
                    body_text=body_text,
                    speaker_notes="",
                    render_path=str(image_path),
                )
            )

    return records


def _parse_pptx(path: Path, render_dir: Path) -> list[SlideRecord]:
    presentation = Presentation(path)
    rendered_paths = _render_pptx_to_images(path, render_dir, len(presentation.slides))

    records: list[SlideRecord] = []
    for ordinal, slide in enumerate(presentation.slides, start=1):
        text_frames: list[str] = []
        table_texts: list[str] = []

        for shape in slide.shapes:
            _collect_shape_text(shape, text_frames, table_texts)

        title = text_frames[0] if text_frames else ""
        body_parts = text_frames[1:] + table_texts

        notes_text = ""
        try:
            notes_text = _normalized_text(slide.notes_slide.notes_text_frame.text)
        except AttributeError:
            notes_text = ""

        records.append(
            SlideRecord(
                ordinal=ordinal,
                kind="slide",
                title=title,
                body_text="\n".join(body_parts),
                speaker_notes=notes_text,
                render_path=rendered_paths[ordinal - 1],
            )
        )

    return records


def _collect_shape_text(
    shape,
    text_frames: list[str],
    table_texts: list[str],
) -> None:
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for child in shape.shapes:
            _collect_shape_text(child, text_frames, table_texts)
        return

    if getattr(shape, "has_text_frame", False):
        text = _normalized_text(shape.text_frame.text)
        if text:
            text_frames.append(text)

    if getattr(shape, "has_table", False):
        cell_text: list[str] = []
        for row in shape.table.rows:
            for cell in row.cells:
                text = _normalized_text(cell.text)
                if text:
                    cell_text.append(text)
        if cell_text:
            table_texts.append("\n".join(cell_text))


def _render_pptx_to_images(
    path: Path,
    render_dir: Path,
    slide_count: int,
) -> list[str | None]:
    soffice = shutil.which("soffice")
    if soffice is None:
        return [None] * slide_count

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        profile_dir = tmp_path / "libreoffice-profile"
        profile_dir.mkdir()
        try:
            subprocess.run(
                [
                    soffice,
                    f"-env:UserInstallation={profile_dir.as_uri()}",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(tmp_path),
                    str(path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return [None] * slide_count

        pdf_path = tmp_path / f"{path.stem}.pdf"
        if not pdf_path.is_file():
            return [None] * slide_count

        rendered = _render_pdf_pages(pdf_path, render_dir, "slide")
        if len(rendered) < slide_count:
            rendered.extend([None] * (slide_count - len(rendered)))
        return rendered[:slide_count]


def _render_pdf_pages(
    path: Path,
    render_dir: Path,
    prefix: str,
) -> list[str]:
    render_dir.mkdir(parents=True, exist_ok=True)

    rendered_paths: list[str] = []
    with fitz.open(path) as document:
        for ordinal, page in enumerate(document, start=1):
            image_path = render_dir / f"{prefix}-{ordinal:04d}.png"
            page.get_pixmap(
                matrix=fitz.Matrix(1.5, 1.5),
                alpha=False,
            ).save(image_path)
            rendered_paths.append(str(image_path))

    return rendered_paths


def _split_title_and_body(text: str) -> tuple[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return "", ""
    return lines[0], "\n".join(lines[1:])


def _normalized_text(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


__all__ = ["UnsupportedFormatError", "parse_source"]
