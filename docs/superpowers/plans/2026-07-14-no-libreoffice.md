# No-LibreOffice PowerPoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove LibreOffice completely while preserving PPTX text and embedded visual assets, then finish exhaustive completeness retrieval and release verification.

**Architecture:** `python-pptx` and OOXML remain the only PPTX readers. Picture blobs become versioned `VisualAsset` records with exact bytes and EMU geometry; PDF pages remain the only full-page renders. Ranked search stays focused, while a cursor-based reader enumerates complete lecture scopes.

**Tech Stack:** Python 3.11+, python-pptx, PyMuPDF, SQLite FTS5, standard-library hashlib/base64/json, pytest, Ruff.

## Global Constraints

- Never invoke, detect, require, or recommend LibreOffice, `soffice`, or `unoconv`.
- Never launch desktop software or a conversion subprocess.
- Preserve exact PPTX text, notes, tables, embedded image bytes, and geometry.
- Do not claim that extracted pictures reproduce full PowerPoint layout.
- Mark layout-dependent content `review-needed`.
- PDF remains the supported pixel-accurate visual format.
- Preserve transactional publication, incremental hashing, citations, and source immutability.
- Use tests first for every behavior change.

---

### Task 1: Embedded PPTX Assets Without A Renderer

**Files:**
- Modify: `src/classcorpus/models.py`
- Modify: `src/classcorpus/parsers.py`
- Modify: `tests/fixtures/make_fixtures.py`
- Modify: `tests/test_parsers.py`

**Interfaces:**
- Produce `VisualAsset(path, kind, shape_name, content_type, left, top, width, height)`.
- Add `SlideRecord.visual_assets: tuple[VisualAsset, ...]`.
- Keep `render_path=None` for every PPTX record.

- [ ] Add failing tests proving:

```python
assert all(record.render_path is None for record in records)
assert records[0].visual_assets
asset = records[0].visual_assets[0]
assert Path(asset.path).read_bytes() == expected_picture_bytes
assert (asset.left, asset.top, asset.width, asset.height) == expected_geometry
```

Patch `subprocess.run` to raise and prove PPTX parsing still succeeds. Add a
grouped picture and repeated image occurrence; assert every shape occurrence
is retained while identical bytes share one generated path.

- [ ] Run `tests/test_parsers.py` and confirm RED because `VisualAsset` does not
exist and PPTX parsing still calls the renderer.

- [ ] Remove `shutil`, `subprocess`, `tempfile`,
`_render_pptx_to_images()`, and PPTX calls to it.

- [ ] Recursively collect pictures:

```python
@dataclass(frozen=True, slots=True)
class VisualAsset:
    path: str
    kind: str
    shape_name: str
    content_type: str
    left: int
    top: int
    width: int
    height: int
```

Hash `shape.image.blob`, write each unique blob atomically to
`render_dir / "assets" / "<sha256>.<ext>"`, and append one `VisualAsset` per
shape occurrence. Recurse through group shapes.

- [ ] Run parser tests and Ruff; commit:

```bash
git commit -m "feat: extract PowerPoint assets without LibreOffice"
```

### Task 2: Persist Assets And Make Vision Honest

**Files:**
- Modify: `src/classcorpus/database.py`
- Modify: `src/classcorpus/search.py`
- Modify: `src/classcorpus/vision.py`
- Modify: `src/classcorpus/indexer.py`
- Modify: `tests/test_database.py`
- Modify: `tests/test_indexer.py`
- Modify: `tests/test_search.py`
- Modify: `tests/test_vision.py`
- Modify: `tests/test_removal.py`

**Interfaces:**
- Add `visual_assets` table keyed by `(slide_id, asset_index)`.
- Add `visual_assets` to `SearchResult`.
- Add `asset_paths`, `assets`, extraction status/reasons, and optional
  `warning` to `VisionItem`.

- [ ] Write failing persistence, cleanup, and queue tests:

```python
assert Path(stored_asset["path"]).read_bytes() == expected
assert search_result.visual_assets[0].shape_name == "Picture 1"
assert queue[0].asset_paths == (stored_asset_path,)
assert queue_without_viewable_source.warning["type"] == "visual-source-unavailable"
```

Assert `store_descriptions()` rejects a slide that has neither a valid PDF
render nor a valid asset path.

- [ ] Add the table:

```sql
CREATE TABLE IF NOT EXISTS visual_assets (
    id INTEGER PRIMARY KEY,
    slide_id INTEGER NOT NULL REFERENCES slides(id) ON DELETE CASCADE,
    asset_index INTEGER NOT NULL CHECK(asset_index >= 0),
    path TEXT NOT NULL,
    kind TEXT NOT NULL,
    shape_name TEXT NOT NULL,
    content_type TEXT NOT NULL,
    left INTEGER NOT NULL,
    top INTEGER NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    UNIQUE(slide_id, asset_index)
);
```

Insert assets in the same `replace_source()` transaction. Extend generated
directory discovery, references, course removal, and pending cleanup to union
PDF render paths and asset paths.

- [ ] Replace `renderer_unavailable` with:

```text
visual-source-unavailable
PowerPoint layout was not rendered. Embedded images remain available; export
the lecture to PDF for pixel-accurate visual review.
```

Only emit it for `review-needed` PPTX records with no asset.

- [ ] Queue review-needed records before other pending records. A queue item is
viewable when a valid `render_path` or at least one valid asset exists.
Preserve reasons when transitioning to `visually-reviewed`.

- [ ] Run database/index/search/vision/removal tests and Ruff; commit:

```bash
git commit -m "feat: persist PowerPoint visual assets"
```

### Task 3: Exhaustive Ordered Retrieval

**Files:**
- Create: `src/classcorpus/records.py`
- Create: `scripts/read_lectures.py`
- Create: `tests/test_records.py`
- Modify: `tests/test_scripts.py`

**Interfaces:**
- Produce `read_records(database, *, course, source_file=None, cursor=None, limit=20) -> RecordPage`.
- Cursor encodes source path plus ordinal in URL-safe base64 JSON.

- [ ] Write failing tests that iterate two sources with duplicate ordinals in
pages of two and prove every `(source_file, ordinal)` appears exactly once.
Test malformed cursors, positive limits, source filters, complete `raw_text`,
asset metadata, scope-wide `total_records`, and `review_needed`.

- [ ] Implement `limit + 1` ordered querying:

```sql
ORDER BY source_files.relative_path, slides.ordinal
```

Continuation compares `(relative_path, ordinal)`. Return `has_more`,
`next_cursor`, `total_records`, `returned_records`, and total scope
`review_needed`.

- [ ] Add `read_lectures.py --course COURSE [--source FILE] [--cursor CURSOR]
[--limit N] --json`, including canonical citations.

- [ ] Run record/script tests and Ruff; commit:

```bash
git commit -m "feat: add exhaustive lecture retrieval"
```

### Task 4: Skill, Public Package, And Proof

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `references/record-schema.md`
- Modify: `references/study-workflows.md`
- Modify: `tests/test_skill.py`
- Create: `docs/architecture.md`
- Create: `docs/privacy.md`
- Create: `ROADMAP.md`
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `examples/README.md`
- Modify: `.superpowers/sdd/progress.md`

- [ ] Add failing skill tests requiring repository `.venv` interpreter
selection, `read_lectures.py` pagination for all/every/full-scope requests,
review-needed disclosure, and no public LibreOffice references.

- [ ] Update public instructions:

```text
Focused question -> ranked search.
Whole lecture/range/all/every -> read_lectures.py until has_more is false.
PPTX -> native text/notes/tables and embedded images, no full-slide rendering.
Exact visual layout -> export to PDF with a tool chosen by the user.
```

- [ ] Add concise architecture, privacy, roadmap, issue templates, and examples
documentation required by the original open-source design.

- [ ] Run:

```bash
.venv/bin/ruff check src scripts tests
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q src scripts tests
git diff --check
rg -i "libreoffice|soffice|unoconv" README.md SKILL.md references src scripts tests
```

The final `rg` must produce no matches.

- [ ] Run isolated real-PDF and generated-PPTX acceptance:
  - subprocess patched to fail for PPTX;
  - exact PPTX slide count, text, notes, tables, asset bytes, geometry;
  - PDF page count and renders;
  - exhaustive pagination covers every record once;
  - second sync skips unchanged files;
  - focused search preserves exact citations;
  - source hashes remain unchanged.

- [ ] Record acceptance evidence and commit:

```bash
git commit -m "docs: complete ClassCorpus open-source release"
```
