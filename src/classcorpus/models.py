from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class SlideRecord:
    ordinal: int
    kind: Literal["slide", "page"]
    title: str
    body_text: str
    speaker_notes: str
    render_path: str | None = None
    visual_description: str | None = None


@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    size: int
    mtime_ns: int
    sha256: str
    parser_version: str
