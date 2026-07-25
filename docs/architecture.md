# Architecture

ClassCorpus is a local Agent Skill, not an application or service. The host
agent handles reasoning; small Python commands provide deterministic storage
and retrieval.

The installed `classcorpus` CLI is the human-facing entry point for course
lifecycle, search, health, and environment diagnostics. Existing scripts
remain stable machine-readable interfaces for agents.

## Data Flow

1. `index_lectures.py` discovers formats registered by parser plugins under a
   course root.
2. Parsers preserve native text and extraction evidence without changing the
   source files.
3. SQLite stores one ordered record per page or slide, plus FTS5 search data
   and optional local embeddings from sentence-transformers, FastEmbed, or a
   dependency-free hashing backend.
4. `search_lectures.py` returns a ranked subset for focused questions.
5. Focused retrieval selects a query-centered 900-character passage;
   `read_record.py` retrieves adjacent chunks only when they are needed.
6. `classcorpus inspect` verifies evidence against the current source hash and
   parser version without mutating the index.
7. Artifact renderers write privacy-preserving provenance manifests, and
   `classcorpus verify-artifact` detects output or cited-source drift.
8. `read_lectures.py` cursor-paginates every record for exhaustive requests.
9. `review_powerpoint.py` inventories layout-dependent records and required
   review actions.
10. Optional local OCR stores separately labeled text, backend, and confidence
   and refreshes FTS without overwriting native extraction.
11. The host agent cites records and optionally adds visual descriptions.

Updates are content-addressed with SHA-256. A changed source is parsed before
its old valid records are replaced, and failed refreshes retain stale evidence
with an explicit warning.

Agent-facing search, read, outline, review, and OCR payloads label all
source-derived fields as untrusted evidence. This preserves source text
verbatim while preventing document instructions from becoming agent authority.

## Format Boundaries

PDF pages provide extracted text and full-page renders. PPTX files provide
native text, speaker notes, tables, embedded image bytes, and image geometry.
They do not provide a pixel-accurate full-slide render. DOCX files provide one
logical document record containing paragraphs, tables, hyperlinks, and OOXML
text because Word pagination is renderer-dependent. Layout-dependent objects
are marked for review instead of being silently treated as complete. Markdown
and plain-text files provide one native-text page record per file. New formats
implement the same `SlideRecord` contract through isolated parser plugins.

Generated data lives outside lecture folders. No network server or provider API
is part of the runtime.

Flashcard rendering and conversion are stateless output helpers. They read
user-selected JSON and write self-contained HTML, CSV, or TSV artifacts without
adding generated study content to the course index. PDF and HTML renderers
also write sidecar manifests with hashes, relative source identity, canonical
citations, and parser versions; absolute source paths and lecture contents are
excluded. Interactive HTML runs entirely in the browser with no network
service or persistent study database.
