from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from classcorpus.models import SlideRecord
from classcorpus.parser_registry import ParserPlugin


def parse_docx_document(path: Path, render_dir: Path) -> list[SlideRecord]:
    del render_dir
    document = Document(path)
    blocks = _document_blocks(document)
    xml_texts = [
        str(node.text)
        for node in document.element.iter()
        if node.tag.endswith("}t") and node.text
    ]
    raw_text = "\n".join(xml_texts)
    structured_text = "\n".join(blocks)
    missing_tokens = _tokens(raw_text) - _tokens(structured_text)

    metadata_title = str(document.core_properties.title or "").strip()
    title = metadata_title or (blocks[0] if blocks else "")
    body_blocks = blocks if metadata_title else blocks[1:]
    body_text = "\n\n".join(body_blocks)

    reasons: list[str] = []
    if not raw_text.strip():
        reasons.append("no-native-text")
    if missing_tokens:
        reasons.append("unmapped-ooxml-text")
    if document.element.xpath(".//*[local-name()='blip']"):
        reasons.append("embedded-image")
    if document.element.xpath(".//*[local-name()='oMath' or local-name()='oMathPara']"):
        reasons.append("equation-or-embedded-object")

    return [
        SlideRecord(
            ordinal=1,
            kind="page",
            title=title,
            body_text=body_text,
            speaker_notes="",
            raw_text=raw_text,
            extraction_status="review-needed" if reasons else "text-extracted",
            extraction_reasons=tuple(reasons),
            native_text_chars=len(raw_text),
            has_visual_content=bool(
                {"embedded-image", "equation-or-embedded-object"} & set(reasons)
            ),
        )
    ]


def _document_blocks(document) -> list[str]:
    blocks: list[str] = []
    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            text = _normalize(item.text)
        elif isinstance(item, Table):
            text = "\n".join(
                " | ".join(_normalize(cell.text) for cell in row.cells)
                for row in item.rows
            ).strip()
        else:
            continue
        if text:
            blocks.append(text)
    return blocks


def _normalize(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _tokens(text: str) -> Counter[str]:
    return Counter(re.findall(r"\w+", text.casefold(), flags=re.UNICODE))


DOCX_PLUGIN = ParserPlugin(
    name="word-documents",
    suffixes=(".docx",),
    parse=parse_docx_document,
)

__all__ = ["DOCX_PLUGIN", "parse_docx_document"]
