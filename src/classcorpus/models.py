from dataclasses import dataclass
from typing import Literal

ExtractionStatus = Literal[
    "text-extracted",
    "review-needed",
    "visually-reviewed",
]


@dataclass(frozen=True, slots=True)
class SlideRecord:
    ordinal: int
    kind: Literal["slide", "page"]
    title: str
    body_text: str
    speaker_notes: str
    raw_text: str = ""
    extraction_status: ExtractionStatus = "review-needed"
    extraction_reasons: tuple[str, ...] = ()
    native_text_chars: int = 0
    has_visual_content: bool = False
    render_path: str | None = None
    visual_description: str | None = None


@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    size: int
    mtime_ns: int
    sha256: str
    parser_version: str
