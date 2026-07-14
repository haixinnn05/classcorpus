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

- Recursive local PDF and PPTX discovery
- Native text, table, and PowerPoint speaker-note extraction
- One-based slide/page records and exact source paths
- Incremental SHA-256 synchronization
- Atomic replacement that preserves valid records after parse failures
- SQLite FTS5 retrieval with optional local embeddings
- Opt-in, agent-native visual slide descriptions
- Cited summaries, comparisons, flashcards, exams, cheat sheets, and plans

## Requirements

- Python 3.11 or newer
- LibreOffice only when rendered PowerPoint images are desired
- No model download for baseline indexing and search

PDF pages render through PyMuPDF. PPTX native content indexes without
LibreOffice; visual analysis for PPTX requires a local `soffice` executable.

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

## Five-Minute Start

Ask the agent:

> Index my Algorithms lectures at `/absolute/path/to/Algorithms`.

The skill runs the equivalent of:

```bash
.venv/bin/python scripts/index_lectures.py \
  "Algorithms" "/absolute/path/to/Algorithms" --json
```

Then ask:

> Explain Bellman-Ford from class and cite the slides.

The agent searches the local index before answering:

```bash
.venv/bin/python scripts/search_lectures.py \
  "Bellman-Ford" --course "Algorithms" --json
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

## Optional Semantic Retrieval

Full-text search works immediately. To add a local sentence-transformer:

```bash
.venv/bin/python -m pip install -e ".[embeddings]"
.venv/bin/python scripts/build_embeddings.py "Algorithms" --json
```

This may download model weights. It is never required for baseline use.

## Remove Generated Course Data

Removal requires explicit confirmation:

```bash
.venv/bin/python scripts/remove_course.py "Algorithms" --confirm --json
```

This deletes only ClassCorpus database rows and rendered cache files. It never
modifies lecture sources.

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
tests/                 Unit and integration tests with generated fixtures
```

## Development

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/ruff check src scripts tests
.venv/bin/python -m pytest -q
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before proposing changes.

## License

Apache License 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
