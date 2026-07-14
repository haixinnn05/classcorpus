import os
import re
import tempfile
from pathlib import Path

import platformdirs


def data_root() -> Path:
    override = os.environ.get("CLASSCORPUS_DATA_DIR")
    root = (
        Path(override)
        if override
        else Path(platformdirs.user_data_dir("ClassCorpus", "ClassCorpus"))
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    return data_root() / "classcorpus.sqlite3"


def render_directory(
    course: str,
    content_hash: str,
    parser_version: str,
) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", course.lower()).strip("-") or "course"
    version = parser_version.encode("utf-8").hex() or "empty"
    return (
        data_root()
        / "renders"
        / slug
        / f"parser-{version}"
        / content_hash
    )


def create_render_generation(
    course: str,
    content_hash: str,
    parser_version: str,
) -> Path:
    root = render_directory(course, content_hash, parser_version)
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="generation-", dir=root))
