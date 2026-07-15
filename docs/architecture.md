# Architecture

ClassCorpus is a local Agent Skill, not an application or service. The host
agent handles reasoning; small Python commands provide deterministic storage
and retrieval.

## Data Flow

1. `index_lectures.py` discovers PDF and PPTX files under a course root.
2. Parsers preserve native text and extraction evidence without changing the
   source files.
3. SQLite stores one ordered record per page or slide, plus FTS5 search data
   and optional local embeddings from sentence-transformers, FastEmbed, or a
   dependency-free hashing backend.
4. `search_lectures.py` returns a ranked subset for focused questions.
5. `read_lectures.py` cursor-paginates every record for exhaustive requests.
6. `review_powerpoint.py` inventories layout-dependent records and required
   review actions.
7. The host agent cites records and optionally adds visual descriptions.

Updates are content-addressed with SHA-256. A changed source is parsed before
its old valid records are replaced, and failed refreshes retain stale evidence
with an explicit warning.

## Format Boundaries

PDF pages provide extracted text and full-page renders. PPTX files provide
native text, speaker notes, tables, embedded image bytes, and image geometry.
They do not provide a pixel-accurate full-slide render. Layout-dependent
objects are marked for review instead of being silently treated as complete.

Generated data lives outside lecture folders. No network server or provider API
is part of the runtime.
