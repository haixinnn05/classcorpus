from __future__ import annotations

import re
from html import unescape
from pathlib import Path

from classcorpus.models import SlideRecord
from classcorpus.parser_registry import ParserPlugin

_TIMING_LINE = re.compile(
    r"^(?P<start>\d{1,3}:\d{2}(?::\d{2})?[.,]\d{3})\s*-->\s*"
    r"(?P<end>\d{1,3}:\d{2}(?::\d{2})?[.,]\d{3})(?:\s+.*)?$"
)
_TAG = re.compile(r"<[^>]+>")


def parse_transcript(path: Path, render_dir: Path) -> list[SlideRecord]:
    del render_dir
    raw = path.read_text(encoding="utf-8-sig")
    suffix = path.suffix.casefold()
    blocks = _blocks(raw)
    if suffix == ".vtt":
        blocks = _vtt_content_blocks(blocks)
    records: list[SlideRecord] = []
    previous_start_ms: int | None = None
    for block_number, block in enumerate(blocks, start=1):
        lines = [line.rstrip() for line in block.splitlines()]
        timing_index = next(
            (index for index, line in enumerate(lines) if "-->" in line),
            None,
        )
        if timing_index is None:
            if suffix == ".srt":
                raise ValueError(f"SRT block {block_number} has no timing line")
            continue
        timing = _TIMING_LINE.fullmatch(lines[timing_index].strip())
        if timing is None:
            raise ValueError(
                f"invalid transcript timing in block {block_number}: "
                f"{lines[timing_index].strip()}"
            )
        start_ms = _timestamp_ms(timing.group("start"))
        end_ms = _timestamp_ms(timing.group("end"))
        if end_ms <= start_ms:
            raise ValueError(f"transcript cue {block_number} must end after it starts")
        if previous_start_ms is not None and start_ms <= previous_start_ms:
            raise ValueError(
                "transcript cue start timestamps must be strictly increasing"
            )
        cue_lines = lines[timing_index + 1 :]
        cue_raw = "\n".join(cue_lines).strip()
        cue_text = _clean_cue_text(cue_raw)
        if not cue_text:
            continue
        previous_start_ms = start_ms
        records.append(
            SlideRecord(
                ordinal=len(records) + 1,
                kind="transcript",
                title="Transcript",
                body_text=cue_text,
                speaker_notes="",
                raw_text=cue_raw,
                extraction_status="text-extracted",
                extraction_reasons=(),
                native_text_chars=len(cue_raw),
                has_visual_content=False,
                start_ms=start_ms,
                end_ms=end_ms,
            )
        )
    if not records:
        raise ValueError(f"transcript contains no timed text cues: {path}")
    return records


def _blocks(raw: str) -> list[str]:
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    return [
        block.strip() for block in re.split(r"\n[ \t]*\n", normalized) if block.strip()
    ]


def _vtt_content_blocks(blocks: list[str]) -> list[str]:
    if not blocks or not blocks[0].splitlines()[0].strip().startswith("WEBVTT"):
        raise ValueError("WebVTT transcript must start with WEBVTT")
    content: list[str] = []
    for block in blocks[1:]:
        first = block.splitlines()[0].strip().upper()
        if first.startswith(("NOTE", "STYLE", "REGION")):
            continue
        content.append(block)
    return content


def _timestamp_ms(value: str) -> int:
    parts = value.replace(",", ".").split(":")
    if len(parts) == 2:
        hours = 0
        minutes_text, seconds_text = parts
    elif len(parts) == 3:
        hours = int(parts[0])
        minutes_text, seconds_text = parts[1:]
    else:
        raise ValueError(f"invalid transcript timestamp: {value}")
    minutes = int(minutes_text)
    seconds, milliseconds = (int(part) for part in seconds_text.split(".", 1))
    if minutes >= 60 or seconds >= 60:
        raise ValueError(f"invalid transcript timestamp: {value}")
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds


def _clean_cue_text(value: str) -> str:
    without_tags = _TAG.sub("", value)
    return "\n".join(
        line.strip() for line in unescape(without_tags).splitlines() if line.strip()
    )


TRANSCRIPT_PLUGIN = ParserPlugin(
    name="timed-transcripts",
    suffixes=(".vtt", ".srt"),
    parse=parse_transcript,
)


__all__ = ["TRANSCRIPT_PLUGIN", "parse_transcript"]
