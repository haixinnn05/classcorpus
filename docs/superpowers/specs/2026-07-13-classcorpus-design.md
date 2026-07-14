# ClassCorpus Design

**Status:** Approved design, pending written-spec review  
**Author:** Jackson Wu  
**Date:** 2026-07-13  
**License:** Apache-2.0

## Summary

ClassCorpus is an open-source, portable AI agent skill that gives Codex, Claude
Code, and other Agent Skills-compatible tools persistent access to a student's
lecture materials.

The skill indexes local PDF and PowerPoint files once, updates only changed
files, and retrieves the smallest relevant set of slides for each request. The
host agent remains responsible for reasoning and generating answers or study
materials. ClassCorpus does not provide its own application, chat interface,
server, or hosted service.

## Problem

Students repeatedly provide the same lecture files to AI agents. This wastes
time and context, makes cross-lecture questions difficult, and often loses
details contained in diagrams, equations, speaker notes, and slide structure.
Answers also lack reliable references to the original lecture and slide.

Existing open-source projects cover much of the broad study-assistant space:

- SlideScholar provides multimodal slide RAG, citations, and study modes, but
  uses a notebook and GPU-oriented ingestion workflow.
- SlideGuide provides a full multimodal tutoring application with a web stack,
  database services, and model providers.
- LectureMindAI provides a local study application with SQLite and FAISS, but
  centers on manual uploads and text extraction.
- Existing lecture Agent Skills generally reread supplied files to produce one
  set of notes or study assets.

ClassCorpus is deliberately narrower. It is the reusable local memory layer for
an existing agent, not another study application.

## Goals

1. Install as a standard agent skill, not as a separate application.
2. Index local PDF and PPTX course folders without a hosted backend.
3. Preserve course, file, lecture, page or slide, text, notes, and source paths.
4. Skip unchanged files using content hashes and parser-version metadata.
5. Search an entire course without loading every source file into agent context.
6. Return exact source metadata for cited answers.
7. Let the active agent add visual descriptions without separate model API keys.
8. Support cited explanations, summaries, flashcards, practice exams, cheat
   sheets, comparisons, and study plans through the host agent.
9. Work on macOS, Windows, and Linux.

## Non-Goals

The first release will not include:

- A web, mobile, desktop, or Streamlit interface
- A custom chatbot or bundled language model
- An HTTP, MCP, or hosted server
- Supabase, PostgreSQL, or cloud storage
- Direct OpenAI, Anthropic, Gemini, or other model API integrations
- Google Drive, OneDrive, LMS, Canvas, or CourseWorks connectors
- Video or audio transcription
- Automatic grading, progress dashboards, or collaborative accounts
- Knowledge graphs

An MCP adapter may be added later, but it must remain a thin interface over the
same local skill data.

## User Experience

After placing the skill in an agent's skill directory, a student interacts with
their existing agent:

> Index my Algorithms course at `~/Courses/Algorithms`.

The agent invokes the bundled indexing script. Later, the student can ask:

> Explain Bellman-Ford from class and cite the slides.

> Compare dynamic programming in lectures 4 and 8.

> Create a cited practice exam for lectures 1 through 6.

> Analyze any slides whose diagrams have not been described yet.

The student does not launch another interface or upload the same files again.
Large generated artifacts may be saved as Markdown or JSON when requested.

## Repository Shape

```text
classcorpus/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── scripts/
│   ├── index_lectures.py
│   ├── search_lectures.py
│   ├── vision_queue.py
│   └── store_visual_description.py
├── references/
│   ├── record-schema.md
│   ├── citation-rules.md
│   └── study-workflows.md
├── tests/
│   ├── fixtures/
│   ├── test_indexing.py
│   ├── test_search.py
│   └── test_vision_queue.py
├── pyproject.toml
├── README.md
├── CONTRIBUTING.md
├── LICENSE
└── NOTICE
```

`SKILL.md` is the canonical cross-agent workflow. `agents/openai.yaml` supplies
Codex-facing metadata but does not change the core behavior. Other agents may
ignore that file and use the same skill instructions and scripts.

## Components

### Skill Instructions

`SKILL.md` will tell an agent when and how to:

- Register and synchronize a local course folder
- Search before answering course-specific questions
- Retrieve additional slides when evidence is insufficient
- Process queued slide images with the agent's own vision capability
- Store visual descriptions for future searches
- Generate study materials from retrieved evidence
- Cite claims and disclose missing or conflicting evidence

The skill must not instruct the agent to read an entire semester into context
for each request.

### Indexing Script

`index_lectures.py` will:

1. Discover `.pdf` and `.pptx` files recursively.
2. Compute a content hash for each source file.
3. Compare the hash and parser version with the local manifest.
4. Skip unchanged files.
5. Extract one structured record per PDF page or PowerPoint slide.
6. Extract PowerPoint speaker notes when available.
7. Render pages or slides when a supported local renderer is available.
8. Replace records atomically after successful processing.
9. Continue after individual file failures and return a structured summary.

PDF extraction and rendering will use PyMuPDF. PPTX native extraction will use
python-pptx. PowerPoint rendering will use LibreOffice in headless mode when it
is available. A missing renderer must not prevent native text indexing.

### Local Storage

SQLite will store:

- Courses and source roots
- Source-file identity, hash, size, modification time, and parser version
- Slide or page records
- Native text, speaker notes, and visual descriptions
- Rendering paths and vision-analysis status
- SQLite FTS5 search content

Generated images and the database will live in an operating-system-appropriate
user data directory selected with `platformdirs`. Lecture source folders remain
unchanged.

Each slide record will include:

```json
{
  "course": "Algorithms",
  "source_file": "Lecture08.pptx",
  "source_path": "/home/student/Courses/Algorithms/Lecture08.pptx",
  "slide_number": 27,
  "title": "Dynamic Programming",
  "body_text": "Top-down recursion\nMemoization",
  "speaker_notes": "Use Fibonacci as an example.",
  "visual_description": null,
  "render_path": ".../Lecture08/slide-027.png",
  "content_hash": "...",
  "parser_version": "1"
}
```

### Search Script

`search_lectures.py` will accept a natural-language query plus optional course,
lecture, and slide filters. It will return machine-readable JSON containing:

- Ranked slide records
- Match snippets and ranking signals
- Exact source paths and slide or page numbers
- Visual-analysis status

SQLite FTS5 will work without model downloads. Optional local embeddings may be
installed as an extra and combined with full-text results. The agent may rerank
the small returned candidate set, but it must not receive the whole index.

### Agent-Native Vision

Visual analysis is opt-in and provider-neutral:

1. `vision_queue.py` returns rendered slides missing visual descriptions.
2. The active Codex or Claude agent views a small batch of images.
3. The agent describes diagrams, charts, equations, annotations, and important
   layout relationships.
4. `store_visual_description.py` validates and stores the descriptions.
5. FTS and optional embeddings include the new descriptions.

The scripts never call a model provider directly. A failed or interrupted batch
remains queued and can resume later.

### Study Workflows

The skill will provide workflows for:

- Cited question answering
- Lecture and multi-lecture summaries
- Lecture comparisons
- Flashcards and Anki-compatible structured output
- Practice exams with answer keys
- Cheat sheets
- Study plans
- Plain-language explanations

These are agent workflows, not separate generation services. Every workflow
must retrieve adequate source coverage before drafting and retain citations in
the output.

## Citation Rules

The canonical human-readable form is:

```text
[Algorithms, Lecture08.pptx, Slide 27]
```

PDF records use `Page` instead of `Slide`. A factual answer based on course
materials must cite the supporting records. If the agent adds general knowledge,
it must label that content as outside the indexed course materials.

The search result must always preserve the absolute source path internally so
the agent can open the original file when the environment supports it.

## Error Handling

- One corrupt file must not stop the remaining sync.
- Failed files must retain their previous valid records until replacement
  succeeds.
- Missing optional rendering or embedding dependencies must produce actionable
  messages and preserve baseline text indexing.
- Unsupported or image-only content must be marked explicitly.
- Search against an empty or stale index must tell the agent to synchronize.
- Destructive course removal must require confirmation and affect only generated
  index data, never lecture source files.
- Scripts must use nonzero exit codes for operational failures and JSON error
  objects when machine-readable output is requested.

## Privacy

- Native extraction, storage, and search are local.
- No telemetry is collected.
- No cloud connector or model API is required.
- Only images selected for opt-in visual analysis are viewed by the active
  agent, subject to that agent's own data policy.
- The skill must warn users not to process confidential or restricted course
  materials through an agent that is not approved for them.
- Removing a course deletes its generated records and render cache after
  confirmation.

## Testing

### Unit Tests

- PDF page extraction
- PPTX text and speaker-note extraction
- File hashing and unchanged-file detection
- Atomic replacement after successful parsing
- FTS indexing and metadata filters
- Citation formatting
- Vision queue and description validation

### Integration Tests

- Index a sample course containing PDF and PPTX files.
- Run the same sync twice and verify that the second run skips every file.
- Modify one source and verify that only that file is reprocessed.
- Query across multiple lectures and verify source metadata.
- Fail one corrupt file without losing other indexed content.
- Remove a course index without modifying source materials.

### Skill Tests

- Validate the skill folder and metadata.
- Exercise the same natural-language requests with Codex and Claude Code.
- Confirm that both agents invoke search before answering.
- Confirm that unsupported claims are labeled rather than presented as course
  facts.

## Acceptance Criteria

The first release is successful when:

1. A user can install the repository as a skill and index a local course folder.
2. PDF pages and PPTX slides retain correct source numbers.
3. Speaker notes are retained for supported PPTX files.
4. A second unchanged sync performs no parsing or rendering.
5. A natural-language query returns relevant slides with exact source metadata.
6. The host agent can answer and generate study materials with citations.
7. The host agent can add visual descriptions without a separate provider key.
8. Baseline operation requires no server, custom UI, or embedding-model download.
9. Tests pass on macOS, Windows, and Linux.

## Release Scope

Version 1 contains only the portable skill, local helper scripts, PDF/PPTX
indexing, SQLite FTS search, optional local embeddings, incremental
synchronization, citations, optional agent-native vision, and study workflows.

Future releases may add additional document formats, an MCP adapter,
cloud-folder discovery, transcripts, and concept relationships. Each addition
must preserve the skill-first, local-default architecture.
