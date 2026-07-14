# Extraction Completeness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent silent lecture-content loss by preserving native text, auditing every page and slide, labeling uncertain extraction, and providing exhaustive ordered retrieval.

**Architecture:** Extend `SlideRecord` and SQLite with lossless extraction evidence, then make PDF/PPTX parsers emit deterministic audit reasons. Keep ranked search for focused questions and add a cursor-based exhaustive reader for full-scope tasks; visual review remains opt-in and prioritizes uncertain records.

**Tech Stack:** Python 3.11+, PyMuPDF, python-pptx/lxml OOXML elements, SQLite FTS5, standard-library JSON/base64 cursors, pytest, Ruff.

## Global Constraints

- ClassCorpus remains an Agent Skill, not an app, UI, server, MCP service, hosted backend, or provider API.
- Index uncertain records instead of blocking them; mark them `review-needed`.
- Never claim perfect OCR or visual interpretation.
- Preserve the exact Unicode strings returned by native parsers without an application-level character limit.
- Produce exactly one record per PDF page or PowerPoint slide with contiguous one-based ordinals.
- Search limits record count only; returned content fields remain complete.
- Full-scope requests must iterate deterministic pagination until `has_more` is false.
- Visual analysis remains opt-in under the active agent's data policy.
- Existing citations, transactional publication, stale-record behavior, incremental hashing, and source-file safety must remain intact.
- All production changes require a failing test first.

---

## File Map

```text
src/classcorpus/models.py             Extraction fields and status literals
src/classcorpus/database.py           Additive migration and full-field persistence
src/classcorpus/parsers.py            Native preservation and structural audits
src/classcorpus/indexer.py            Parser version, review warnings, aggregate counts
src/classcorpus/search.py             Expose completeness evidence in ranked results
src/classcorpus/records.py            Ordered exhaustive retrieval and cursor contract
src/classcorpus/vision.py             Prioritized review queue and reviewed transition
scripts/index_lectures.py             Existing index JSON gains aggregate counts
scripts/search_lectures.py            Existing search JSON gains review warnings
scripts/read_lectures.py              New exhaustive reader command
scripts/vision_queue.py               Existing queue exposes extraction evidence
tests/fixtures/make_fixtures.py       Adversarial PDF/PPTX fixtures
tests/test_database.py                Migration and lossless round-trip tests
tests/test_parsers.py                 Native and OOXML audit tests
tests/test_indexer.py                 Review counts and warning tests
tests/test_search.py                  Complete result-field tests
tests/test_records.py                 Cursor and no-gap pagination tests
tests/test_scripts.py                 Agent-facing JSON contract tests
tests/test_vision.py                  Review priority and status transition tests
tests/test_skill.py                   Exhaustive workflow and interpreter guidance
SKILL.md                              Focused versus exhaustive agent workflow
references/record-schema.md           New fields, statuses, reasons, and cursor contract
references/study-workflows.md         Full-scope coverage ledger requirements
README.md                             User-facing completeness semantics and commands
```

### Task 1: Lossless Record Model And Additive Migration

**Files:**
- Modify: `src/classcorpus/models.py`
- Modify: `src/classcorpus/database.py`
- Modify: `tests/test_database.py`
- Modify: `tests/test_search.py`

**Interfaces:**
- Produces: `ExtractionStatus`, expanded `SlideRecord`, additive `Database.initialize()` migration.
- Consumes: Existing `SlideRecord` storage and FTS publication.

- [ ] **Step 1: Write failing model and migration tests**

Add a round-trip test using a long string with indentation and blank lines:

```python
def test_replace_source_preserves_lossless_extraction_fields(tmp_path):
    raw = "Title\n\n  indented detail\n" + ("x" * 120_000) + "\n"
    db = Database(tmp_path / "db.sqlite3")
    db.initialize()
    course = db.upsert_course("Algorithms", tmp_path / "lectures")
    record = SlideRecord(
        ordinal=1,
        kind="page",
        title="Title",
        body_text="indented detail",
        speaker_notes="",
        raw_text=raw,
        extraction_status="review-needed",
        extraction_reasons=("embedded-image",),
        native_text_chars=len(raw),
        has_visual_content=True,
    )

    db.replace_source(
        course.id,
        "lecture.pdf",
        tmp_path / "lectures" / "lecture.pdf",
        SourceFingerprint(1, 1, "abc", "2"),
        [record],
    )

    row = db.connection.execute("SELECT * FROM slides").fetchone()
    assert row["raw_text"] == raw
    assert json.loads(row["extraction_reasons"]) == ["embedded-image"]
    assert row["native_text_chars"] == len(raw)
    assert row["has_visual_content"] == 1
```

Add a migration test that creates the previous `slides` schema, inserts one
row, calls `initialize()`, and expects:

```python
assert row["raw_text"] == "Legacy title\nLegacy body"
assert row["extraction_status"] == "review-needed"
assert json.loads(row["extraction_reasons"]) == ["legacy-record-not-audited"]
assert row["native_text_chars"] == len(row["raw_text"])
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_database.py::test_replace_source_preserves_lossless_extraction_fields \
  tests/test_database.py::test_initialize_migrates_legacy_slides_for_review -q
```

Expected: FAIL because `SlideRecord` and `slides` do not have the new fields.

- [ ] **Step 3: Expand the immutable record**

Implement in `models.py`:

```python
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
```

- [ ] **Step 4: Add the schema columns and idempotent migration**

Add these columns to new databases:

```sql
raw_text TEXT NOT NULL DEFAULT '',
extraction_status TEXT NOT NULL DEFAULT 'review-needed'
    CHECK(extraction_status IN (
        'text-extracted', 'review-needed', 'visually-reviewed'
    )),
extraction_reasons TEXT NOT NULL DEFAULT '[]',
native_text_chars INTEGER NOT NULL DEFAULT 0 CHECK(native_text_chars >= 0),
has_visual_content INTEGER NOT NULL DEFAULT 0
    CHECK(has_visual_content IN (0, 1)),
```

After `executescript(SCHEMA)`, call `_migrate_slides()`:

```python
def _migrate_slides(self) -> None:
    columns = {
        row["name"]
        for row in self.connection.execute("PRAGMA table_info(slides)")
    }
    additions = {
        "raw_text": "TEXT NOT NULL DEFAULT ''",
        "extraction_status": "TEXT NOT NULL DEFAULT 'review-needed'",
        "extraction_reasons": (
            "TEXT NOT NULL DEFAULT '[\"legacy-record-not-audited\"]'"
        ),
        "native_text_chars": "INTEGER NOT NULL DEFAULT 0",
        "has_visual_content": "INTEGER NOT NULL DEFAULT 0",
    }
    added = False
    for name, declaration in additions.items():
        if name not in columns:
            self.connection.execute(
                f"ALTER TABLE slides ADD COLUMN {name} {declaration}"
            )
            added = True
    if added:
        self.connection.execute(
            """
            UPDATE slides
            SET raw_text = CASE
                    WHEN body_text = '' THEN title
                    WHEN title = '' THEN body_text
                    ELSE title || char(10) || body_text
                END,
                extraction_status = 'review-needed',
                extraction_reasons = '["legacy-record-not-audited"]'
            """
        )
        self.connection.execute(
            "UPDATE slides SET native_text_chars = length(raw_text)"
        )
```

Do not interpolate user input; the interpolated identifiers and declarations
come only from the fixed local dictionary.

- [ ] **Step 5: Persist new fields transactionally**

Extend the `slides` insert in `replace_source()`:

```python
reasons_json = json.dumps(
    slide.extraction_reasons,
    ensure_ascii=True,
    separators=(",", ":"),
)
```

Insert `raw_text`, `extraction_status`, `extraction_reasons`,
`native_text_chars`, and `int(slide.has_visual_content)` in the same database
transaction as the relational and FTS rows.

- [ ] **Step 6: Update manual `SlideRecord` and `SearchResult` fixtures**

Keep defaults where the old tests are not asserting completeness. Explicitly
set the fields in tests that verify JSON output or database persistence.

- [ ] **Step 7: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m pytest tests/test_database.py tests/test_search.py -q
.venv/bin/ruff check src/classcorpus/models.py src/classcorpus/database.py \
  tests/test_database.py tests/test_search.py
```

Expected: focused suites pass and Ruff reports no errors.

```bash
git add src/classcorpus/models.py src/classcorpus/database.py \
  tests/test_database.py tests/test_search.py
git commit -m "feat: preserve extraction completeness evidence"
```

### Task 2: PDF And PowerPoint Completeness Audits

**Files:**
- Modify: `tests/fixtures/make_fixtures.py`
- Modify: `tests/test_parsers.py`
- Modify: `src/classcorpus/parsers.py`

**Interfaces:**
- Consumes: Expanded `SlideRecord`.
- Produces: `parse_source(path, render_dir) -> list[SlideRecord]` with lossless
  text, status, reasons, and visual-content evidence.

- [ ] **Step 1: Add adversarial fixtures and failing PDF tests**

Create a PDF fixture with:

```python
raw_text = "Long lecture\n\n" + ("precise-content " * 10_000)
page.insert_textbox(fitz.Rect(30, 30, 580, 760), raw_text, fontsize=6)
```

Create a second page containing a raster image and less than 80 native
characters. Assert:

```python
assert len(records) == document.page_count
assert [record.ordinal for record in records] == list(
    range(1, document.page_count + 1)
)
assert records[0].raw_text.endswith("precise-content")
assert len(records[0].raw_text) > 100_000
assert records[1].extraction_status == "review-needed"
assert "low-native-text" in records[1].extraction_reasons
assert "embedded-image" in records[1].extraction_reasons
```

Use a generated textbox that actually fits all text; if PyMuPDF reports a
negative remainder, split the long content across multiple inserted text
blocks on the same page rather than accepting clipped fixture content.

- [ ] **Step 2: Add failing PPTX audit tests**

Extend the fixture with nested group text, table cells, notes, a picture, and
an OOXML `<a:t>` run that is not exposed as a normal shape text frame. Assert:

```python
assert len(records) == len(Presentation(source).slides)
assert records[0].raw_text.count("OOXML fallback detail") == 1
assert "OOXML fallback detail" in records[0].body_text
assert "unmapped-ooxml-text" in records[0].extraction_reasons
assert records[0].extraction_status == "review-needed"
assert records[0].speaker_notes == "Exact instructor note."
assert records[0].native_text_chars == len(records[0].raw_text)
```

- [ ] **Step 3: Run parser tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_parsers.py -q
```

Expected: FAIL on missing raw text and audit fields.

- [ ] **Step 4: Preserve PDF native text and compare extractors**

Add focused helpers:

```python
def _tokens(text: str) -> Counter[str]:
    return Counter(re.findall(r"\w+", text.casefold(), flags=re.UNICODE))


def _pdf_audit(page: fitz.Page, raw_text: str) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    images = bool(page.get_images(full=True))
    drawings = bool(page.get_drawings())
    word_text = " ".join(str(word[4]) for word in page.get_text("words"))
    block_text = "\n".join(
        str(block[4]) for block in page.get_text("blocks")
        if len(block) > 4
    )
    native_tokens = _tokens(raw_text)
    if _tokens(word_text) - native_tokens or _tokens(block_text) - native_tokens:
        reasons.append("native-extractor-disagreement")
    if not raw_text.strip():
        reasons.append("no-native-text")
    elif images and len(raw_text.strip()) < 80:
        reasons.append("low-native-text")
        reasons.append("embedded-image")
    return images or drawings, tuple(dict.fromkeys(reasons))
```

Use `page.get_text("text", sort=True)` as `raw_text`. Derive normalized
`title` and `body_text` from it without modifying `raw_text`.

- [ ] **Step 5: Add OOXML census and visual-feature detection**

Use each slide's existing XML element, not assumptions about `slide1.xml`
filenames:

```python
def _xml_texts(element) -> list[str]:
    return [
        node.text
        for node in element.iter()
        if node.tag.endswith("}t") and node.text
    ]


def _missing_texts(census: list[str], extracted: list[str]) -> list[str]:
    remaining = Counter(text.strip() for text in extracted if text.strip())
    missing: list[str] = []
    for text in (item.strip() for item in census):
        if not text:
            continue
        if remaining[text]:
            remaining[text] -= 1
        else:
            missing.append(text)
    return missing
```

Build `raw_text` from the slide OOXML census in source order. Compare it to
high-level text frames and tables. Append unique unmapped text to `body_text`
and add `unmapped-ooxml-text`.

Inspect shape types, XML tags, and relationship suffixes for pictures,
charts/diagram data, `m:oMath`, and OLE objects. Add the corresponding reason
without attempting to infer the visual's meaning.

- [ ] **Step 6: Assign deterministic statuses**

Use one helper for both formats:

```python
def _status(reasons: tuple[str, ...]) -> ExtractionStatus:
    return "review-needed" if reasons else "text-extracted"
```

Do not use a floating-point confidence score. Visual presence alone sets
`has_visual_content`; only explicit audit reasons change the status.

- [ ] **Step 7: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m pytest tests/test_parsers.py -q
.venv/bin/ruff check src/classcorpus/parsers.py \
  tests/fixtures/make_fixtures.py tests/test_parsers.py
```

Expected: parser tests pass, including exact long-text preservation and record
count checks.

```bash
git add src/classcorpus/parsers.py tests/fixtures/make_fixtures.py \
  tests/test_parsers.py
git commit -m "feat: audit PDF and PowerPoint extraction"
```

### Task 3: Index And Search Completeness Reporting

**Files:**
- Modify: `src/classcorpus/indexer.py`
- Modify: `src/classcorpus/search.py`
- Modify: `scripts/search_lectures.py`
- Modify: `tests/test_indexer.py`
- Modify: `tests/test_search.py`
- Modify: `tests/test_scripts.py`

**Interfaces:**
- Consumes: Audited `SlideRecord` fields.
- Produces: `SyncReport.records_indexed`, `records_review_needed`, and ranked
  `SearchResult` completeness fields.

- [ ] **Step 1: Write failing report and search tests**

Assert an indexed mixed-content fixture reports:

```python
assert report.records_indexed == 2
assert report.records_review_needed == 1
warning = next(
    item for item in report.warnings
    if item["type"] == "extraction_review_needed"
)
assert warning["ordinal"] == "2"
assert "embedded-image" in warning["reasons"]
```

Assert a ranked search result returns the full 120,000-character field while
its preview remains shorter:

```python
result = search(database, "precise-content", limit=1)[0]
assert len(result.raw_text) > 100_000
assert len(result.snippet) < len(result.raw_text)
assert result.extraction_status in {"text-extracted", "review-needed"}
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_indexer.py tests/test_search.py tests/test_scripts.py -q
```

Expected: FAIL because reports and search results omit completeness evidence.

- [ ] **Step 3: Extend reports and bump the parser version**

Set:

```python
PARSER_VERSION = "2"
```

Extend `SyncReport`:

```python
records_indexed: int
records_review_needed: int
```

For every newly parsed record, increment totals and emit one warning:

```python
if slide.extraction_status == "review-needed":
    source_warnings.append(
        {
            "path": str(source),
            "ordinal": str(slide.ordinal),
            "type": "extraction_review_needed",
            "reasons": list(slide.extraction_reasons),
            "message": (
                f"{slide.kind.title()} {slide.ordinal} may contain content "
                "that native extraction did not fully capture."
            ),
        }
    )
```

Remove the old separate `image_only` loop; `no-native-text` now covers it.

- [ ] **Step 4: Expose completeness fields through both search queries**

Add to `SearchResult` and the SELECT lists in `search()` and
`_results_by_id()`:

```text
raw_text
extraction_status
extraction_reasons
native_text_chars
has_visual_content
```

Decode `extraction_reasons` from JSON before constructing `SearchResult`.
Use one `_row_to_search_result(row)` helper so FTS and semantic-only paths
cannot drift.

- [ ] **Step 5: Add returned-evidence warnings to the search script**

When any result needs review, append:

```python
{
    "type": "extraction_review_needed",
    "course": result.course,
    "source_file": result.source_file,
    "ordinal": str(result.ordinal),
    "reasons": list(result.extraction_reasons),
    "message": "Returned evidence may have incomplete native extraction.",
}
```

Keep `sync_required` reserved for absent or failed sources. Review-needed
evidence does not force a sync because re-indexing the same file cannot recover
visual meaning.

- [ ] **Step 6: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_indexer.py tests/test_search.py tests/test_scripts.py -q
.venv/bin/ruff check src/classcorpus/indexer.py \
  src/classcorpus/search.py scripts/search_lectures.py \
  tests/test_indexer.py tests/test_search.py tests/test_scripts.py
```

Expected: tests pass; existing citation and stale-source assertions remain
unchanged.

```bash
git add src/classcorpus/indexer.py src/classcorpus/search.py \
  scripts/search_lectures.py tests/test_indexer.py tests/test_search.py \
  tests/test_scripts.py
git commit -m "feat: report uncertain lecture extraction"
```

### Task 4: Exhaustive Ordered Lecture Reader

**Files:**
- Create: `src/classcorpus/records.py`
- Create: `scripts/read_lectures.py`
- Create: `tests/test_records.py`
- Modify: `tests/test_scripts.py`

**Interfaces:**
- Produces: `LectureRecord`, `RecordPage`, and
  `read_records(database, *, course, source_file=None, cursor=None, limit=20)`.
- Consumes: Existing course/source/slide schema and citation formatting.

`LectureRecord` contains course, source file/path/status/error, ordinal, kind,
all stored text and extraction fields, visual description, render path, and
vision status. It intentionally omits ranked-search-only `snippet` and `score`.

- [ ] **Step 1: Write failing pagination tests**

Create two sources with overlapping ordinals and assert:

```python
seen: list[tuple[str, int]] = []
cursor = None
while True:
    page = read_records(
        database,
        course="Algorithms",
        cursor=cursor,
        limit=2,
    )
    seen.extend((record.source_file, record.ordinal) for record in page.records)
    if not page.has_more:
        break
    assert page.next_cursor is not None
    cursor = page.next_cursor

assert seen == [
    ("Lecture01.pdf", 1),
    ("Lecture01.pdf", 2),
    ("Lecture02.pptx", 1),
    ("Lecture02.pptx", 2),
]
assert len(seen) == len(set(seen))
assert page.total_records == 4
```

Add tests for invalid cursors, positive limits, source filtering, full raw-text
fields, and a final page with `has_more is False` and `next_cursor is None`.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_records.py -q
```

Expected: collection FAIL because `classcorpus.records` does not exist.

- [ ] **Step 3: Implement an opaque deterministic cursor**

Use URL-safe base64 JSON:

```python
def _encode_cursor(source_file: str, ordinal: int) -> str:
    payload = json.dumps(
        {"source_file": source_file, "ordinal": ordinal},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[str, int]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded))
        source_file = str(value["source_file"])
        ordinal = int(value["ordinal"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise ValueError("invalid lecture record cursor") from error
    if not source_file or ordinal < 1:
        raise ValueError("invalid lecture record cursor")
    return source_file, ordinal
```

Also catch `binascii.Error` in the final implementation.

- [ ] **Step 4: Implement ordered `limit + 1` retrieval**

Query by course and optional source. Apply continuation with:

```sql
AND (
    source_files.relative_path > ?
    OR (
        source_files.relative_path = ?
        AND slides.ordinal > ?
    )
)
ORDER BY source_files.relative_path, slides.ordinal
LIMIT ?
```

Fetch `limit + 1`, return only the first `limit`, and derive `has_more` from
the extra row. Run separate aggregate queries for `total_records` and total
`review_needed` in the requested scope; cursor position must not change those
totals.

- [ ] **Step 5: Add the agent-facing script**

Implement arguments:

```python
parser.add_argument("--course", required=True)
parser.add_argument("--source")
parser.add_argument("--cursor")
parser.add_argument("--limit", type=int, default=20)
parser.add_argument("--json", action="store_true", dest="json_mode")
```

Emit:

```python
{
    "ok": True,
    "records": [
        {**asdict(record), "citation": format_citation(record)}
        for record in page.records
    ],
    "total_records": page.total_records,
    "returned_records": len(page.records),
    "has_more": page.has_more,
    "next_cursor": page.next_cursor,
    "review_needed": page.review_needed,
    "warnings": list(page.warnings),
}
```

- [ ] **Step 6: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m pytest tests/test_records.py tests/test_scripts.py -q
.venv/bin/ruff check src/classcorpus/records.py scripts/read_lectures.py \
  tests/test_records.py tests/test_scripts.py
```

Expected: pagination returns every `(source_file, ordinal)` exactly once and
the script works from an unrelated current directory.

```bash
git add src/classcorpus/records.py scripts/read_lectures.py \
  tests/test_records.py tests/test_scripts.py
git commit -m "feat: add exhaustive lecture record retrieval"
```

### Task 5: Prioritized Visual Review

**Files:**
- Modify: `src/classcorpus/vision.py`
- Modify: `tests/test_vision.py`
- Modify: `tests/test_scripts.py`

**Interfaces:**
- Consumes: `extraction_status`, `extraction_reasons`, and existing renders.
- Produces: review-first vision queue and `visually-reviewed` transition.

- [ ] **Step 1: Write failing queue and transition tests**

Prepare records in source order where a later record is `review-needed`.
Assert:

```python
items = get_vision_queue(database, "Algorithms", limit=3)
assert items[0].extraction_status == "review-needed"
assert items[0].extraction_reasons == ("embedded-image",)

store_descriptions(
    database,
    [{"slide_id": items[0].slide_id, "description": "A labeled graph."}],
)
row = database.connection.execute(
    """
    SELECT extraction_status, extraction_reasons
    FROM slides WHERE id = ?
    """,
    (items[0].slide_id,),
).fetchone()
assert row["extraction_status"] == "visually-reviewed"
assert json.loads(row["extraction_reasons"]) == ["embedded-image"]
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_vision.py -q
```

Expected: FAIL because queue items lack completeness fields and source order
currently wins over review priority.

- [ ] **Step 3: Prioritize review-needed records**

Add fields to `VisionItem`, decode reasons through a row helper, and order:

```sql
ORDER BY
    CASE slides.extraction_status
        WHEN 'review-needed' THEN 0
        ELSE 1
    END,
    source_files.relative_path,
    slides.ordinal
```

Keep filtering missing render files after the query. Do not mark an item
reviewed merely because it was queued.

- [ ] **Step 4: Preserve reasons while completing visual review**

Extend the existing update:

```sql
UPDATE slides
SET visual_description = ?,
    vision_status = 'complete',
    extraction_status = 'visually-reviewed'
WHERE id = ?
```

Do not clear or rewrite `extraction_reasons`.

- [ ] **Step 5: Verify GREEN and commit**

Run:

```bash
.venv/bin/python -m pytest tests/test_vision.py tests/test_scripts.py -q
.venv/bin/ruff check src/classcorpus/vision.py \
  tests/test_vision.py tests/test_scripts.py
```

Expected: uncertain records are first, stored descriptions remove them from
the queue, and reason history remains.

```bash
git add src/classcorpus/vision.py tests/test_vision.py tests/test_scripts.py
git commit -m "feat: prioritize uncertain slides for visual review"
```

### Task 6: Agent Workflow, Contracts, And Acceptance

**Files:**
- Modify: `tests/test_skill.py`
- Modify: `SKILL.md`
- Modify: `references/record-schema.md`
- Modify: `references/study-workflows.md`
- Modify: `README.md`
- Modify: `.superpowers/sdd/progress.md`

**Interfaces:**
- Consumes: `read_lectures.py`, extraction statuses, review warnings.
- Produces: deterministic agent behavior for focused and exhaustive requests.

- [ ] **Step 1: Record a baseline skill-behavior failure**

Before editing `SKILL.md`, dispatch a fresh agent without the proposed new
guidance using this scenario:

```text
You have a ClassCorpus course containing 35 pages. Search returned eight
results. The user asks: "Create a complete study guide covering every page."
What commands do you run and when do you begin writing?
```

Record whether it begins writing from the top eight results or lacks a
deterministic termination condition. This is the RED evidence required for a
skill-document behavior change.

- [ ] **Step 2: Write failing static contract tests**

Add:

```python
def test_skill_uses_exhaustive_reader_for_full_scope_requests(skill_text):
    assert "read_lectures.py" in skill_text
    assert "has_more" in skill_text
    assert "next_cursor" in skill_text
    assert "all" in skill_text.lower()
    assert "every" in skill_text.lower()


def test_skill_discloses_uncertain_extraction(skill_text):
    assert "review-needed" in skill_text
    assert "Do not describe native extraction as complete" in skill_text


def test_skill_prefers_repository_virtual_environment(skill_text):
    assert ".venv/bin/python" in skill_text
    assert ".venv\\Scripts\\python.exe" in skill_text
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_skill.py -q
```

Expected: FAIL because exhaustive retrieval and venv selection are not
documented.

- [ ] **Step 4: Update the skill with a positive workflow contract**

Define interpreter selection:

```text
Prefer "$SKILL_DIR/.venv/bin/python" on macOS/Linux or
"$SKILL_DIR/.venv/Scripts/python.exe" on Windows. Fall back to an environment
Python 3 only when the repository venv does not exist.
```

Define the two retrieval modes:

```text
Focused question -> search_lectures.py with a small ranked limit.
Whole lecture/range or "all"/"every" -> read_lectures.py, beginning without a
cursor and repeating with next_cursor until has_more is false.
```

Require the agent to keep a source/ordinal coverage ledger and disclose the
returned `review_needed` count. Do not describe native extraction as complete
when any requested record is `review-needed`.

- [ ] **Step 5: Update public JSON and study-workflow contracts**

Document every new record field and status in `record-schema.md`. Add a complete
`read_lectures.py` response example with two records, `has_more`, and
`next_cursor`.

In `study-workflows.md`, require:

```text
1. Determine the full requested source scope.
2. Iterate read_lectures.py until has_more is false.
3. Verify returned unique records equals total_records.
4. Draft only after coverage is complete.
5. Disclose remaining review-needed records.
```

Explain in `README.md` that search snippets are previews while content fields
and exhaustive reading are not truncated.

- [ ] **Step 6: Re-run the skill scenario with the updated skill**

Dispatch a fresh agent with `SKILL.md` available and the same 35-page scenario.
Pass only if it:

1. chooses `read_lectures.py`;
2. follows `next_cursor`;
3. waits for `has_more: false`;
4. checks total unique coverage;
5. discloses review-needed records before claiming completeness.

- [ ] **Step 7: Run the complete automated verification**

Run:

```bash
.venv/bin/ruff check src scripts tests
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q src scripts tests
git diff --check
```

Expected: all checks pass with no warnings or whitespace errors.

- [ ] **Step 8: Run real-PDF acceptance in isolated state**

Run:

```bash
ACCEPTANCE_ROOT="$(mktemp -d /tmp/classcorpus-completeness.XXXXXX)"
mkdir -p "$ACCEPTANCE_ROOT/course" "$ACCEPTANCE_ROOT/data"
cp "/Users/haixinwu/Downloads/LectureLens_Design_Document.pdf" \
  "$ACCEPTANCE_ROOT/course/"
CLASSCORPUS_DATA_DIR="$ACCEPTANCE_ROOT/data" \
  .venv/bin/python scripts/index_lectures.py \
  "Lecture Intelligence" "$ACCEPTANCE_ROOT/course" --json
```

Then iterate `read_lectures.py` with a small `--limit 3`, passing each returned
`next_cursor` until `has_more` is false. Verify:

```text
unique (source_file, ordinal) count == total_records == PDF page count
sum(len(raw_text) for every returned record) ==
    sum(length(raw_text) in SQLite)
every record has extraction_status and extraction_reasons
focused search citations still name the exact PDF page
second index reports skipped: 1
```

Request one `review-needed` item from `vision_queue.py`, inspect its rendered
image under the approved data policy, store a description with
`store_visual_description.py`, and verify the record becomes
`visually-reviewed` while its original extraction reasons remain present.

Record commands and observed counts in `.superpowers/sdd/progress.md`.

- [ ] **Step 9: Commit the workflow and acceptance evidence**

```bash
git add SKILL.md README.md references/record-schema.md \
  references/study-workflows.md tests/test_skill.py \
  .superpowers/sdd/progress.md
git commit -m "docs: require complete lecture coverage"
```

### Task 7: Independent Review And Release Gate

**Files:**
- Modify only if review finds a tested defect.

**Interfaces:**
- Consumes: Completed implementation and acceptance evidence.
- Produces: Release-ready branch with no unresolved correctness findings.

- [ ] **Step 1: Request independent spec-compliance review**

Give the reviewer:

```text
Review implementation against:
docs/superpowers/specs/2026-07-14-extraction-completeness-design.md

Prioritize silent truncation, missing ordinals, migration data loss, invalid
cursor behavior, misleading completeness claims, and privacy regressions.
Return findings with file and line references, or READY.
```

- [ ] **Step 2: Request independent code-quality review**

Review transaction safety, malformed OOXML/PDF behavior, cursor validation,
cross-platform paths, JSON compatibility, and test gaps. Any fix must begin
with a failing regression test and receive its own commit.

- [ ] **Step 3: Run final verification after all review fixes**

Run:

```bash
.venv/bin/ruff check src scripts tests
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q src scripts tests
git diff --check
git status --short
```

Expected: all checks pass and the worktree is clean.
