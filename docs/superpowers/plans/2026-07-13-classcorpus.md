# ClassCorpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a portable Agent Skill that incrementally indexes local PDF/PPTX lecture folders and gives existing agents cited slide-level retrieval and opt-in visual analysis.

**Architecture:** Keep `SKILL.md` as the product entry point. Bundled Python scripts call a small internal library for parsing, SQLite storage, indexing, retrieval, optional embeddings, and vision-queue persistence; the host agent performs all reasoning and content generation.

**Tech Stack:** Python 3.11+, PyMuPDF, python-pptx, SQLite FTS5, platformdirs, optional sentence-transformers/numpy, pytest, Ruff, GitHub Actions.

## Global Constraints

- This repository is an Agent Skill, never a web, desktop, mobile, Streamlit, or chatbot application.
- Do not add an HTTP server, MCP server, hosted backend, telemetry, or direct model-provider API.
- Baseline indexing and search must work without an embedding-model download.
- Store generated data outside lecture folders using `platformdirs`; support `CLASSCORPUS_DATA_DIR` for deterministic tests.
- Preserve exact source path and one-based PDF page or PowerPoint slide numbers.
- Skip unchanged files using SHA-256 plus parser version.
- Never delete or modify lecture source files.
- A corrupt source file must not stop the remaining sync.
- Vision analysis is opt-in and performed by the active agent from queued local images.
- Support macOS, Windows, and Linux.

---

## File Map

```text
SKILL.md                              Canonical agent workflow
agents/openai.yaml                    Codex display metadata
pyproject.toml                        Python dependencies and test/lint settings
src/classcorpus/models.py             Shared immutable records
src/classcorpus/paths.py              OS data paths and render paths
src/classcorpus/database.py           Schema, transactions, FTS, course lifecycle
src/classcorpus/parsers.py            PDF/PPTX extraction and rendering
src/classcorpus/indexer.py            Discovery, hashing, incremental synchronization
src/classcorpus/search.py             FTS and optional hybrid ranking
src/classcorpus/embeddings.py         Optional local vector generation/storage
src/classcorpus/vision.py             Vision queue and description persistence
src/classcorpus/citations.py          Stable human-readable citations
scripts/index_lectures.py             Agent-facing indexing command
scripts/search_lectures.py            Agent-facing retrieval command
scripts/build_embeddings.py           Optional semantic-index command
scripts/vision_queue.py               Agent-facing visual-work queue
scripts/store_visual_description.py   Agent-facing visual-result command
references/record-schema.md           JSON contracts
references/citation-rules.md          Grounding requirements
references/study-workflows.md         Cited study-output procedures
tests/fixtures/                        Generated fixture sources
tests/test_*.py                        Unit and integration coverage
README.md                              Public installation and five-minute start
CONTRIBUTING.md                        Contributor workflow
LICENSE                               Apache-2.0 text
NOTICE                                Attribution notice
.github/workflows/test.yml            Cross-platform CI
```

### Task 1: Skill And Python Foundation

**Files:**
- Create: `SKILL.md`
- Create: `agents/openai.yaml`
- Create: `pyproject.toml`
- Create: `src/classcorpus/__init__.py`
- Create: `src/classcorpus/models.py`
- Create: `src/classcorpus/paths.py`
- Create: `tests/test_paths.py`

**Interfaces:**
- Produces: `SlideRecord`, `SourceFingerprint`, `data_root()`, and `database_path()`.
- Consumes: Nothing.

- [ ] **Step 1: Initialize the skill metadata**

Run the official skill initializer in a temporary directory, then move only its
validated `SKILL.md` and `agents/openai.yaml` scaffolds into the repository:

```bash
python /Users/haixinwu/.codex/skills/.system/skill-creator/scripts/init_skill.py \
  classcorpus --path /tmp/classcorpus-skill \
  --resources scripts,references \
  --interface display_name="ClassCorpus" \
  --interface short_description="Search local lecture folders with exact citations" \
  --interface default_prompt="Use ClassCorpus to index or search my local course materials."
```

Expected: `/tmp/classcorpus-skill/classcorpus/SKILL.md` and
`agents/openai.yaml` exist.

- [ ] **Step 2: Write the failing path tests**

```python
def test_data_root_honors_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path))
    assert data_root() == tmp_path
    assert database_path() == tmp_path / "classcorpus.sqlite3"


def test_render_directory_is_stable(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path))
    assert render_directory("Algorithms", "abc123") == (
        tmp_path / "renders" / "algorithms" / "abc123"
    )
```

- [ ] **Step 3: Run the tests and confirm failure**

Run: `pytest tests/test_paths.py -v`

Expected: FAIL because `classcorpus.paths` does not exist.

- [ ] **Step 4: Add the minimal models and paths**

```python
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
```

```python
def data_root() -> Path:
    override = os.environ.get("CLASSCORPUS_DATA_DIR")
    root = Path(override) if override else Path(
        platformdirs.user_data_dir("ClassCorpus", "ClassCorpus")
    )
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    return data_root() / "classcorpus.sqlite3"


def render_directory(course: str, content_hash: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", course.lower()).strip("-") or "course"
    return data_root() / "renders" / slug / content_hash
```

Set project metadata to Python `>=3.11`, add runtime dependencies
`PyMuPDF>=1.24,<2`, `python-pptx>=1.0,<2`, and `platformdirs>=4,<5`, and add
pytest/Ruff under the `dev` extra.

- [ ] **Step 5: Verify and commit**

Run: `pytest tests/test_paths.py -v && ruff check src tests`

Expected: all tests pass and Ruff reports no errors.

```bash
git add SKILL.md agents pyproject.toml src/classcorpus tests/test_paths.py
git commit -m "chore: scaffold ClassCorpus skill"
```

### Task 2: SQLite Schema And Course Lifecycle

**Files:**
- Create: `src/classcorpus/database.py`
- Create: `tests/test_database.py`

**Interfaces:**
- Consumes: `database_path()`.
- Produces: `Database`, `Course`, `Database.initialize()`,
  `Database.upsert_course(name, source_root)`, and
  `Database.remove_course(name)`.

- [ ] **Step 1: Write failing lifecycle tests**

```python
def test_course_lifecycle(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    db.initialize()
    course = db.upsert_course("Algorithms", tmp_path / "lectures")
    assert course.name == "Algorithms"
    assert course.source_root == str((tmp_path / "lectures").resolve())
    assert db.remove_course("Algorithms") is True
    assert db.remove_course("Algorithms") is False


def test_schema_enables_fts(tmp_path):
    db = Database(tmp_path / "db.sqlite3")
    db.initialize()
    names = db.connection.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
    ).fetchall()
    assert ("slide_fts",) in names
```

- [ ] **Step 2: Confirm failure**

Run: `pytest tests/test_database.py -v`

Expected: FAIL because `Database` is undefined.

- [ ] **Step 3: Implement the schema and transaction boundary**

Create tables `courses`, `source_files`, `slides`, and FTS5 table `slide_fts`.
Use foreign keys with `ON DELETE CASCADE`, unique
`(course_id, relative_path)`, and unique `(source_file_id, ordinal)`.

```python
@dataclass(frozen=True, slots=True)
class Course:
    id: int
    name: str
    source_root: str


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.row_factory = sqlite3.Row

    def initialize(self) -> None:
        self.connection.executescript(SCHEMA)

    def upsert_course(self, name: str, source_root: Path) -> Course:
        root = str(source_root.expanduser().resolve())
        with self.connection:
            self.connection.execute(
                """INSERT INTO courses(name, source_root) VALUES (?, ?)
                   ON CONFLICT(name) DO UPDATE SET source_root=excluded.source_root""",
                (name, root),
            )
        row = self.connection.execute(
            "SELECT id, name, source_root FROM courses WHERE name=?", (name,)
        ).fetchone()
        return Course(**dict(row))
```

`remove_course()` must delete database records and return whether a row existed;
generated render cleanup is added after index paths are available.

- [ ] **Step 4: Verify and commit**

Run: `pytest tests/test_database.py -v`

Expected: all lifecycle and FTS schema tests pass.

```bash
git add src/classcorpus/database.py tests/test_database.py
git commit -m "feat: add local course database"
```

### Task 3: PDF And PowerPoint Parsing

**Files:**
- Create: `src/classcorpus/parsers.py`
- Create: `tests/fixtures/make_fixtures.py`
- Create: `tests/test_parsers.py`

**Interfaces:**
- Consumes: `SlideRecord`, `render_directory()`.
- Produces: `parse_source(path, render_dir) -> list[SlideRecord]` and
  `UnsupportedFormatError`.

- [ ] **Step 1: Generate deterministic fixtures**

Create a two-page PDF with PyMuPDF and a two-slide PPTX with python-pptx. Put
text on every page/slide and speaker notes on slide 2 using the supported
python-pptx notes API. Generate fixtures during tests rather than committing
binary files.

- [ ] **Step 2: Write failing parser tests**

```python
def test_pdf_preserves_pages_and_renders(pdf_fixture, tmp_path):
    records = parse_source(pdf_fixture, tmp_path / "renders")
    assert [(r.kind, r.ordinal) for r in records] == [("page", 1), ("page", 2)]
    assert "Bellman-Ford" in records[1].body_text
    assert Path(records[0].render_path).is_file()


def test_pptx_preserves_slides_and_notes(pptx_fixture, tmp_path):
    records = parse_source(pptx_fixture, tmp_path / "renders")
    assert [(r.kind, r.ordinal) for r in records] == [
        ("slide", 1), ("slide", 2)
    ]
    assert records[1].speaker_notes == "Use Fibonacci as the example."
```

- [ ] **Step 3: Confirm failure**

Run: `pytest tests/test_parsers.py -v`

Expected: FAIL because `parse_source` is undefined.

- [ ] **Step 4: Implement native extraction and best-effort rendering**

```python
def parse_source(path: Path, render_dir: Path) -> list[SlideRecord]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(path, render_dir)
    if suffix == ".pptx":
        return _parse_pptx(path, render_dir)
    raise UnsupportedFormatError(suffix)
```

For PDF, call `page.get_text("text")`, render with
`page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)`, and save
`page-0001.png`.

For PPTX, walk shapes in z-order, collect text frames and table cell text,
select the first non-empty text frame as title, and read
`slide.notes_slide.notes_text_frame.text`. If `soffice` exists, convert the
deck to PDF in a temporary directory and render its pages to
`slide-0001.png`; otherwise set `render_path=None` without failing extraction.

- [ ] **Step 5: Verify and commit**

Run: `pytest tests/test_parsers.py -v`

Expected: PDF and PPTX tests pass; rendering assertions are skipped only for
PPTX when LibreOffice is absent.

```bash
git add src/classcorpus/parsers.py tests/fixtures tests/test_parsers.py
git commit -m "feat: parse PDF and PowerPoint lectures"
```

### Task 4: Incremental Atomic Indexing

**Files:**
- Create: `src/classcorpus/indexer.py`
- Modify: `src/classcorpus/database.py`
- Create: `tests/test_indexer.py`

**Interfaces:**
- Consumes: `Database`, `parse_source()`, `SourceFingerprint`.
- Produces: `sync_course(db, name, source_root) -> SyncReport`.

- [ ] **Step 1: Write failing incremental tests**

```python
def test_second_sync_skips_unchanged_files(course_fixture, database):
    first = sync_course(database, "Algorithms", course_fixture)
    second = sync_course(database, "Algorithms", course_fixture)
    assert first.indexed == 2
    assert second.indexed == 0
    assert second.skipped == 2


def test_corrupt_file_does_not_remove_valid_records(course_fixture, database):
    sync_course(database, "Algorithms", course_fixture)
    pdf = course_fixture / "lecture-1.pdf"
    pdf.write_bytes(b"not a pdf")
    report = sync_course(database, "Algorithms", course_fixture)
    assert report.failed == 1
    assert database.slide_count("Algorithms") > 0
```

- [ ] **Step 2: Confirm failure**

Run: `pytest tests/test_indexer.py -v`

Expected: FAIL because `sync_course` is undefined.

- [ ] **Step 3: Implement hashing, discovery, and replacement**

```python
PARSER_VERSION = "1"


def fingerprint(path: Path) -> SourceFingerprint:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    stat = path.stat()
    return SourceFingerprint(stat.st_size, stat.st_mtime_ns,
                             digest.hexdigest(), PARSER_VERSION)
```

Discover sorted files with suffixes `{".pdf", ".pptx"}`. Parse each changed
file completely before opening the database replacement transaction. In one
transaction, replace that source file's slide rows and FTS rows, then mark the
source status `ready`. On failure, retain old slide rows and record the error.
Return:

```python
@dataclass(frozen=True, slots=True)
class SyncReport:
    indexed: int
    skipped: int
    failed: int
    failures: tuple[dict[str, str], ...]
```

- [ ] **Step 4: Verify and commit**

Run: `pytest tests/test_indexer.py -v`

Expected: unchanged sync skips all files and corrupt replacement retains valid
records.

```bash
git add src/classcorpus/database.py src/classcorpus/indexer.py tests/test_indexer.py
git commit -m "feat: add incremental lecture synchronization"
```

### Task 5: Search And Citations

**Files:**
- Create: `src/classcorpus/search.py`
- Create: `src/classcorpus/citations.py`
- Create: `tests/test_search.py`

**Interfaces:**
- Consumes: populated `slide_fts`.
- Produces: `search(db, query, course=None, limit=8) -> list[SearchResult]` and
  `format_citation(result) -> str`.

- [ ] **Step 1: Write failing retrieval tests**

```python
def test_search_returns_ranked_slide_metadata(indexed_course):
    results = search(indexed_course, "shortest path negative edge")
    assert results[0].source_file == "Lecture08.pptx"
    assert results[0].ordinal == 27
    assert results[0].kind == "slide"


def test_citation_uses_slide_or_page():
    assert format_citation(slide_result) == (
        "[Algorithms, Lecture08.pptx, Slide 27]"
    )
    assert format_citation(page_result) == (
        "[Algorithms, handout.pdf, Page 3]"
    )
```

- [ ] **Step 2: Confirm failure**

Run: `pytest tests/test_search.py -v`

Expected: FAIL because search interfaces are undefined.

- [ ] **Step 3: Implement FTS retrieval**

Define `SearchResult` with `slide_id`, `course`, `source_file`,
`source_path`, `ordinal`, `kind`, `title`, `body_text`, `speaker_notes`,
`visual_description`, `render_path`, `vision_status`, `snippet`, and `score`.
Query FTS5 with `bm25(slide_fts)` and `snippet()`, join metadata tables, apply
course filters as SQL parameters, and convert lower BM25 values into descending
scores by using `-bm25`.

Reject blank queries with `ValueError("query must not be blank")`.

- [ ] **Step 4: Verify and commit**

Run: `pytest tests/test_search.py -v`

Expected: ranked records and exact citations pass.

```bash
git add src/classcorpus/search.py src/classcorpus/citations.py tests/test_search.py
git commit -m "feat: add cited full-text lecture search"
```

### Task 6: Optional Local Embeddings

**Files:**
- Create: `src/classcorpus/embeddings.py`
- Modify: `src/classcorpus/search.py`
- Modify: `pyproject.toml`
- Create: `tests/test_embeddings.py`

**Interfaces:**
- Consumes: slide searchable text and `SearchResult`.
- Produces: `build_embeddings(db, course, encoder) -> int` and hybrid search
  when stored vectors are available.

- [ ] **Step 1: Write tests with a fake encoder**

```python
class FakeEncoder:
    model_name = "fake-v1"

    def encode(self, texts):
        return np.asarray([
            [1.0, 0.0] if "memoization" in text.lower() else [0.0, 1.0]
            for text in texts
        ], dtype=np.float32)


def test_embeddings_are_optional(indexed_course):
    assert search(indexed_course, "memoization")


def test_hybrid_search_uses_stored_vectors(indexed_course):
    count = build_embeddings(indexed_course, "Algorithms", FakeEncoder())
    assert count > 0
    results = search(
        indexed_course, "cached recursion", encoder=FakeEncoder()
    )
    assert results[0].title == "Dynamic Programming"
```

- [ ] **Step 2: Confirm failure**

Run: `pytest tests/test_embeddings.py -v`

Expected: baseline test passes and embedding interface test fails.

- [ ] **Step 3: Implement vector persistence and rank fusion**

Add optional extra:

```toml
embeddings = [
  "numpy>=2,<3",
  "sentence-transformers>=3,<4",
]
```

Store normalized float32 vectors as BLOBs keyed by
`(slide_id, model_name)`. Implement reciprocal-rank fusion with constant 60:

```python
def reciprocal_rank_fusion(rankings: list[list[int]]) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, slide_id in enumerate(ranking, start=1):
            scores[slide_id] = scores.get(slide_id, 0.0) + 1.0 / (60 + rank)
    return scores
```

If numpy or sentence-transformers is unavailable, baseline FTS behavior must
remain unchanged and the script must explain how to install `[embeddings]`.

- [ ] **Step 4: Verify and commit**

Run: `pytest tests/test_embeddings.py tests/test_search.py -v`

Expected: fake-vector hybrid ranking passes without downloading a model.

```bash
git add pyproject.toml src/classcorpus/embeddings.py src/classcorpus/search.py tests/test_embeddings.py
git commit -m "feat: add optional semantic retrieval"
```

### Task 7: Agent-Native Vision Queue

**Files:**
- Create: `src/classcorpus/vision.py`
- Modify: `src/classcorpus/database.py`
- Create: `tests/test_vision.py`

**Interfaces:**
- Consumes: indexed slide records and render paths.
- Produces: `get_vision_queue(db, course, limit) -> list[VisionItem]` and
  `store_descriptions(db, descriptions) -> int`.

- [ ] **Step 1: Write failing queue tests**

```python
def test_queue_only_returns_rendered_pending_slides(indexed_course):
    items = get_vision_queue(indexed_course, "Algorithms", limit=10)
    assert items
    assert all(Path(item.render_path).is_file() for item in items)


def test_storing_description_removes_item_and_updates_search(indexed_course):
    item = get_vision_queue(indexed_course, "Algorithms", limit=1)[0]
    store_descriptions(indexed_course, [
        {"slide_id": item.slide_id,
         "description": "A red-black tree rotation diagram."}
    ])
    assert item.slide_id not in {
        queued.slide_id
        for queued in get_vision_queue(indexed_course, "Algorithms", limit=20)
    }
    assert search(indexed_course, "red-black rotation")[0].slide_id == item.slide_id
```

- [ ] **Step 2: Confirm failure**

Run: `pytest tests/test_vision.py -v`

Expected: FAIL because vision interfaces are undefined.

- [ ] **Step 3: Implement resumable persistence**

Return only records with a real render path and empty visual description.
Validate descriptions as non-empty strings of at least 10 characters, update
the slide and matching FTS row in one transaction, and leave omitted or invalid
items queued.

- [ ] **Step 4: Verify and commit**

Run: `pytest tests/test_vision.py tests/test_search.py -v`

Expected: queue shrinks after storage and new visual text is searchable.

```bash
git add src/classcorpus/database.py src/classcorpus/vision.py tests/test_vision.py
git commit -m "feat: add agent-native visual analysis queue"
```

### Task 8: Agent-Facing Scripts And JSON Contracts

**Files:**
- Create: `scripts/index_lectures.py`
- Create: `scripts/search_lectures.py`
- Create: `scripts/build_embeddings.py`
- Create: `scripts/vision_queue.py`
- Create: `scripts/store_visual_description.py`
- Create: `references/record-schema.md`
- Create: `tests/test_scripts.py`

**Interfaces:**
- Consumes: all library interfaces from Tasks 1-7.
- Produces: stable command-line JSON consumed by `SKILL.md`.

- [ ] **Step 1: Write subprocess contract tests**

```python
def test_index_script_returns_json(course_fixture, env):
    result = run_script(
        "index_lectures.py", "Algorithms", str(course_fixture), "--json", env=env
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["indexed"] == 2


def test_search_script_returns_citations(env):
    result = run_script(
        "search_lectures.py", "memoization", "--course", "Algorithms",
        "--json", env=env
    )
    payload = json.loads(result.stdout)
    assert payload["results"][0]["citation"].startswith("[Algorithms,")
```

- [ ] **Step 2: Confirm failure**

Run: `pytest tests/test_scripts.py -v`

Expected: FAIL because scripts do not exist.

- [ ] **Step 3: Implement thin argparse wrappers**

Every script must:

- Locate the repository `src` directory without depending on current working
  directory.
- Initialize the database.
- Emit `{"ok": true, ...}` on success with `--json`.
- Emit `{"ok": false, "error": {"type": ..., "message": ...}}` and exit 1 on
  operational failure.
- Avoid stack traces in normal agent-facing output.

`store_visual_description.py` accepts `--input PATH`, where the JSON document is
`{"descriptions": [{"slide_id": 1, "description": "..."}]}`. Document every
field and exit code in `references/record-schema.md`.

- [ ] **Step 4: Verify and commit**

Run: `pytest tests/test_scripts.py -v`

Expected: all commands produce valid JSON independent of working directory.

```bash
git add scripts references/record-schema.md tests/test_scripts.py
git commit -m "feat: expose stable skill script contracts"
```

### Task 9: Portable Skill Workflows

**Files:**
- Replace: `SKILL.md`
- Update: `agents/openai.yaml`
- Create: `references/citation-rules.md`
- Create: `references/study-workflows.md`
- Create: `tests/test_skill.py`

**Interfaces:**
- Consumes: script contracts from Task 8.
- Produces: cross-agent indexing, search, vision, and study workflows.

- [ ] **Step 1: Write skill-content tests**

```python
def test_skill_requires_retrieval_before_course_answers(skill_text):
    assert "search_lectures.py" in skill_text
    assert "Do not answer a course-specific claim before searching" in skill_text


def test_skill_forbids_application_surfaces(skill_text):
    forbidden = ("web server", "custom chatbot", "hosted backend")
    assert all(f"Do not create a {item}" in skill_text for item in forbidden)


def test_skill_documents_visual_consent(skill_text):
    assert "Ask for confirmation before visual analysis" in skill_text
```

- [ ] **Step 2: Confirm failure**

Run: `pytest tests/test_skill.py -v`

Expected: FAIL against the generated scaffold.

- [ ] **Step 3: Write the complete agent workflow**

Keep `SKILL.md` below 500 lines and use imperative instructions. Its description
must trigger for indexing lecture folders, answering from course materials,
cross-lecture comparison, study guides, flashcards, practice exams, cheat
sheets, and visual slide analysis.

Define this mandatory sequence:

1. Synchronize when the course is new or the user says files changed.
2. Search with metadata filters before making course-specific claims.
3. Retrieve additional evidence when results are weak or conflicting.
4. Cite every course-derived claim using the returned `citation`.
5. Label general knowledge as outside the course materials.
6. Ask for confirmation before submitting slide images to the active agent's
   vision capability.
7. Generate study artifacts only after retrieving coverage across the requested
   lecture range.

Move detailed schemas and study-output formats into the three reference files.
Regenerate `agents/openai.yaml` using the official generator and validate the
skill:

```bash
python /Users/haixinwu/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py \
  . --interface display_name="ClassCorpus" \
  --interface short_description="Search local lectures with exact citations" \
  --interface default_prompt="Use ClassCorpus to answer from my indexed course materials."
python /Users/haixinwu/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```

Expected: validation succeeds.

- [ ] **Step 4: Verify and commit**

Run: `pytest tests/test_skill.py -v`

Expected: workflow guardrail tests pass.

```bash
git add SKILL.md agents references tests/test_skill.py
git commit -m "feat: define portable course-memory workflows"
```

### Task 10: Privacy, Removal, Documentation, And CI

**Files:**
- Modify: `src/classcorpus/database.py`
- Create: `scripts/remove_course.py`
- Create: `tests/test_removal.py`
- Create: `README.md`
- Create: `CONTRIBUTING.md`
- Create: `LICENSE`
- Create: `NOTICE`
- Create: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: course lifecycle and generated render paths.
- Produces: confirmed generated-data removal and public contributor workflow.

- [ ] **Step 1: Write destructive-boundary tests**

```python
def test_remove_course_deletes_generated_data_not_sources(indexed_course, source):
    original = source.read_bytes()
    assert remove_course(indexed_course, "Algorithms", confirmed=False) is False
    assert remove_course(indexed_course, "Algorithms", confirmed=True) is True
    assert source.read_bytes() == original
```

- [ ] **Step 2: Confirm failure**

Run: `pytest tests/test_removal.py -v`

Expected: FAIL because confirmed removal is undefined.

- [ ] **Step 3: Implement and document removal**

Require `--confirm` in `remove_course.py`. Delete database records and generated
render directories recorded for that course. Resolve every generated path and
verify it is under `data_root()` before deleting it. Never derive a deletion
target from the source root.

Write a five-minute README flow that installs the skill and dependencies,
indexes sample files, searches, and processes a vision queue. State prominently:
“ClassCorpus is an Agent Skill, not an application.” Add privacy and restricted
material warnings. Add Apache-2.0 license text and a NOTICE naming Jackson Wu.

CI must run on `ubuntu-latest`, `macos-latest`, and `windows-latest` with Python
3.11 and 3.12:

```yaml
- run: python -m pip install -e ".[dev]"
- run: ruff check src scripts tests
- run: pytest -q
```

`tests/test_skill.py` provides the cross-platform metadata and workflow checks
in CI. The official skill validator remains an additional local release gate
because its installation path is specific to the contributor's agent setup.

- [ ] **Step 4: Run the complete release gate**

Run:

```bash
ruff check src scripts tests
pytest -q
python /Users/haixinwu/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
git diff --check
```

Expected: lint clean, all tests pass, skill validation succeeds, and no
whitespace errors are reported.

- [ ] **Step 5: Commit**

```bash
git add src/classcorpus/database.py scripts/remove_course.py tests/test_removal.py \
  README.md CONTRIBUTING.md LICENSE NOTICE .github/workflows/test.yml
git commit -m "docs: prepare ClassCorpus for open source"
```

## Final Acceptance Run

- [ ] Create a temporary course containing generated PDF and PPTX fixtures.
- [ ] Index it and record the JSON report.
- [ ] Repeat indexing and verify every source is skipped.
- [ ] Search one text concept and verify exact page/slide citations.
- [ ] Queue one rendered image, store an agent-authored visual description, and
      verify that description becomes searchable.
- [ ] Generate a cited study guide through the installed skill.
- [ ] Run the complete test, lint, and skill-validation commands on the clean
      working tree.
