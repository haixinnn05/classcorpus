from __future__ import annotations

from pathlib import Path

from classcorpus.models import SlideRecord
from classcorpus.parser_registry import ParserPlugin


def parse_text_document(path: Path, render_dir: Path) -> list[SlideRecord]:
    del render_dir
    raw_text = path.read_text(encoding="utf-8")
    lines = raw_text.splitlines()
    title_index = next(
        (index for index, line in enumerate(lines) if line.strip()),
        None,
    )
    if title_index is None:
        title = ""
        body_text = ""
        reasons = ("no-native-text",)
    else:
        title_line = lines[title_index].strip()
        title = (
            title_line.lstrip("#").strip()
            if path.suffix.casefold() == ".md" and title_line.startswith("#")
            else title_line
        )
        body_text = "\n".join(
            line.rstrip()
            for index, line in enumerate(lines)
            if index != title_index
        ).strip()
        reasons = ()
    return [
        SlideRecord(
            ordinal=1,
            kind="page",
            title=title,
            body_text=body_text,
            speaker_notes="",
            raw_text=raw_text,
            extraction_status="review-needed" if reasons else "text-extracted",
            extraction_reasons=reasons,
            native_text_chars=len(raw_text),
            has_visual_content=False,
        )
    ]


TEXT_PLUGIN = ParserPlugin(
    name="text-documents",
    suffixes=(".md", ".txt"),
    parse=parse_text_document,
)

__all__ = ["TEXT_PLUGIN", "parse_text_document"]

