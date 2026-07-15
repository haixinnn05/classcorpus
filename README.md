# ClassCorpus

ClassCorpus is an open-source Agent Skill that gives Codex, Claude Code, and
other Agent Skills-compatible assistants persistent, citation-aware access to
local lecture materials.

**ClassCorpus is an Agent Skill, not an application.** It has no web interface,
custom chatbot, hosted backend, account, telemetry, or required model API.

## What It Solves

Index a semester of PDF and PowerPoint lectures once. The active agent can then
retrieve only the relevant slides or pages, answer with exact citations, and
create grounded study materials without repeatedly loading every source file.

ClassCorpus provides:

- Recursive local PDF, PPTX, Markdown, and plain-text discovery
- Native text, table, and PowerPoint speaker-note extraction
- One-based slide/page records and exact source paths
- Incremental SHA-256 synchronization
- Atomic replacement that preserves valid records after parse failures
- Explicit stale-source warnings when a refresh fails
- SQLite FTS5 retrieval with optional local embeddings
- Cursor-based exhaustive reading without model-selected omissions
- Exact embedded PowerPoint image bytes and placement metadata
- Opt-in, agent-native visual slide descriptions
- Cited summaries, comparisons, flashcards, exams, cheat sheets, and plans
- Optional polished PDF study guides with human-readable math notation

## Requirements

- Python 3.11 or newer
- No model download for baseline indexing and search

PDF pages render through PyMuPDF. PPTX files are read directly with
`python-pptx` and OOXML: text, notes, tables, and embedded images are preserved
without launching desktop software. UTF-8 Markdown and text files are indexed
as one cited page per file through an isolated parser plugin. PowerPoint
charts, equations, SmartArt, OLE objects, and exact slide composition may
require review. Export a presentation to PDF with a tool of your choice when
pixel-accurate full-slide evidence is required.

## Install As A Skill

Clone or place this repository at the skill location used by the agent:

```text
Codex:       ~/.codex/skills/classcorpus/
Claude Code: ~/.claude/skills/classcorpus/
```

Create an isolated Python environment inside the repository:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

On Windows, use `.venv\Scripts\python.exe` instead.

Restart or reload the agent so it discovers `SKILL.md`.

Install the optional PDF renderer when you want printable study guides:

```bash
.venv/bin/python -m pip install -e ".[pdf]"
.venv/bin/python scripts/render_study_guide.py guide.md guide.pdf
```

Verify the installation:

```bash
.venv/bin/classcorpus doctor
```

On Windows, run `.venv\Scripts\classcorpus.exe doctor`.

## Five-Minute Start

Ask the agent:

> Index my Algorithms lectures at `/absolute/path/to/Algorithms`.

For direct use:

```bash
.venv/bin/classcorpus index \
  "Algorithms" "/absolute/path/to/Algorithms"
```

Then ask:

> Explain Bellman-Ford from class and cite the slides.

Search the local index:

```bash
.venv/bin/classcorpus search \
  "Bellman-Ford" --course "Algorithms"
```

Search ranking rewards complete query coverage, exact phrases, and title
matches. A misspelling with no result returns a local "Did you mean" suggestion
without silently changing the query.

Search is token-efficient by default: it returns at most six compact candidates
within a 1,200 estimated-token budget. Then read bounded chunks from only the
selected record:

```bash
.venv/bin/classcorpus search \
  "Bellman-Ford" --course "Algorithms" --json
.venv/bin/classcorpus read \
  "Algorithms" "handout.pdf" 3 \
  --field searchable --json
```

Compact output keeps citations, warnings, extraction state, ranking signals,
and bounded evidence while deduplicating source metadata. `--compact` remains
accepted for compatibility. Use `--full` to request the pre-0.3 complete search
payload.

Follow `next_offset` with `--offset` only when more evidence is needed. Stored
lecture evidence is never truncated. Agents can use `scripts/read_record.py`
for the equivalent stable JSON contract.

Inspect course health and recommended next actions:

```bash
.venv/bin/classcorpus status --course "Algorithms"
```

Agents continue to use the stable `scripts/*.py --json` contracts documented
in [references/record-schema.md](references/record-schema.md).

For a complete summary or anything asking for all/every/whole lecture detail,
start with the compact coverage ledger:

```bash
.venv/bin/classcorpus outline "Algorithms" --json
```

Follow `next_cursor` until `has_more` is false, then expand only the ranges
needed for the artifact. When every complete record is explicitly necessary,
iterate the ordered reader:

```bash
.venv/bin/python scripts/read_lectures.py \
  --course "Algorithms" --source "Lecture08.pptx" --json
.venv/bin/python scripts/read_lectures.py \
  --course "Algorithms" --source "Lecture08.pptx" \
  --cursor "NEXT_CURSOR_FROM_PREVIOUS_RESPONSE" --json
```

The response reports `total_records`, `returned_records`, scope-wide
`review_needed`, and warnings. Each record contains full `raw_text`, extraction
evidence, visual assets, and a canonical citation.

Limit retrieval to one lecture and slide/page when needed:

```bash
.venv/bin/python scripts/search_lectures.py \
  "memoization" --course "Algorithms" \
  --source "Lecture08.pptx" --ordinal 27 --json
```

Expected citations look like:

```text
[Algorithms, Lecture08.pptx, Slide 27]
[Algorithms, handout.pdf, Page 3]
```

## Visual Slide Analysis

Visual analysis is opt-in because images are viewed by the active agent under
that agent's data policy.

After confirmation, the agent requests a small batch:

```bash
.venv/bin/python scripts/vision_queue.py "Algorithms" --limit 5 --json
```

It describes the returned diagrams, equations, charts, annotations, and layout,
then stores those descriptions locally with
`scripts/store_visual_description.py`. Interrupted work remains queued.

For PowerPoint review planning, inspect the complete layout-risk inventory:

```bash
.venv/bin/python scripts/review_powerpoint.py \
  "Algorithms" --source "Lecture08.pptx" --json
```

The report groups records by extraction reason and reviewability, paginates
without hiding total counts, and tells the agent whether to inspect embedded
assets or request a PDF export for full-slide evidence.

## Optional Semantic Retrieval

Full-text search works immediately. For a dependency-free local vector index,
use deterministic feature hashing:

```bash
.venv/bin/python scripts/build_embeddings.py \
  "Algorithms" --backend hashing --dimensions 384 --json
.venv/bin/python scripts/search_lectures.py \
  "cached recursion" --course "Algorithms" --semantic \
  --backend hashing --dimensions 384 --json
```

Hashing improves fuzzy lexical matching but is not a learned semantic model.
For learned local embeddings, install one optional backend:

```bash
# sentence-transformers
.venv/bin/python -m pip install -e ".[embeddings]"

# FastEmbed
.venv/bin/python -m pip install -e ".[fastembed]"
```

Then pass `--backend sentence-transformers` or `--backend fastembed` to both
the build and search commands. Learned backends may download model weights on
first use; inference and vector storage remain local. Embeddings are never
required for baseline indexing or search.

## Optional Local OCR

OCR is opt-in and runs locally. Install the Python adapter plus the Tesseract
executable provided by your operating system:

```bash
.venv/bin/python -m pip install -e ".[ocr]"
.venv/bin/python scripts/run_ocr.py \
  "Algorithms" --backend tesseract --language eng --json
```

The command processes a small resumable batch of PDF renders or embedded PPTX
assets. OCR text becomes searchable while remaining separate from native text.
Every result reports its backend and a `0` to `1` confidence computed from the
mean accepted Tesseract word confidence. This value is not calibrated factual
certainty; inspect low-confidence text and original visual evidence. No image
or extracted text is sent to a network service.

## Flashcard Interchange

Convert agent-generated cited cards among JSON, CSV, and TSV:

```bash
.venv/bin/python scripts/convert_flashcards.py \
  cards.json cards.tsv --json
```

The helper preserves multiline content, citations, and tags. It writes
atomically and refuses to replace an existing file unless `--overwrite` is
explicit. See
[references/flashcard-formats.md](references/flashcard-formats.md) for the
normalized schema and delimited-file rules.

## Remove Generated Course Data

Removal requires explicit confirmation:

```bash
.venv/bin/python scripts/remove_course.py "Algorithms" --confirm --json
```

This deletes only ClassCorpus database rows and generated cache files. It never
modifies lecture sources.

If a refresh fails, ClassCorpus keeps the last valid extracted records but
marks them as stale in search JSON until synchronization succeeds.

## Privacy

- Extraction, indexing, storage, and search are local.
- No telemetry or provider API is built into the scripts.
- Generated data uses the operating system's user data directory.
- Set `CLASSCORPUS_DATA_DIR` to choose another generated-data location.
- Only opt-in visual batches are viewed by the active agent.
- Do not process confidential, restricted, or copyrighted materials through an
  agent unless its data handling is approved for those materials.

## Repository Structure

```text
SKILL.md               Agent workflow and boundaries
scripts/               Stable agent-facing commands
src/classcorpus/       Local parsing, storage, indexing, and retrieval library
references/            JSON, citation, and study-workflow contracts
examples/              Reproducible local usage walkthrough
tests/                 Unit and integration tests with generated fixtures
benchmarks/            Published synthetic extraction/retrieval benchmark
```

See [docs/architecture.md](docs/architecture.md), [docs/privacy.md](docs/privacy.md),
and [ROADMAP.md](ROADMAP.md) for design boundaries and planned work.

## Development

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/ruff check benchmarks src scripts tests
.venv/bin/python -m pytest -q
.venv/bin/python -m benchmarks.run
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes.
See [benchmarks/README.md](benchmarks/README.md) for the corpus, metrics, and
machine-readable benchmark contract.
See [references/parser-plugins.md](references/parser-plugins.md) for the parser
extension contract and built-in text format semantics.
See [references/cli.md](references/cli.md) for unified CLI and diagnostic
semantics.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
