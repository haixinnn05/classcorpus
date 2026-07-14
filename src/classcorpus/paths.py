import os
import re
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


def render_directory(course: str, content_hash: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", course.lower()).strip("-") or "course"
    return data_root() / "renders" / slug / content_hash
