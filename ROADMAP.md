# Roadmap

ClassCorpus prioritizes verifiable extraction and citations over adding an
application surface. It will remain an Agent Skill and local library: a hosted
service, custom chatbot, and required provider API are out of scope.

This roadmap lists work that is wanted but not yet done. Items are not promises,
and the order can change. If you want to take one on, open an issue first so the
approach can be agreed before code is written. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Formats

- **HTML and EPUB** for online textbooks and course sites.

## Study Outputs

- **Deep-linked citations** that open the cited source at the exact page from
  generated HTML and PDF artifacts.

## Instruction Budget

- **Keep converting instructions into affordances.** Every token in `SKILL.md` is
  charged against every workflow and is only a request the agent may ignore, while
  a command is a guarantee. Prefer adding a command that enforces a rule over
  prose that asks for it, and keep payload mechanics in the references.

## Under Consideration

- **A local stdio MCP server** wrapping the existing retrieval contracts, so
  ClassCorpus works in editors and assistants that speak MCP rather than Agent
  Skills. This would not add a web server, hosted backend, or provider API, but
  it does widen the project's surface, so it needs a decision before work
  starts.

## Completed

- A validated Claude Code plugin and self-hosted marketplace manifest, plus a
  package-environment script launcher that keeps pipx and plugin workflows usable
- Skill installation for Claude Code, Codex, Gemini CLI, and GitHub Copilot CLI
- Subprocess-aware branch coverage with an 85% total gate, including real CLI
  execution instead of treating `cli.py` as untouched
- PEP 561 type information and a clean mypy gate across the public library
- Ruff Bugbear and import-order linting plus repository-wide format checks
- Python 3.13 quality CI, default benchmark CI, and clean-wheel smoke tests on
  Linux, macOS, and Windows
- Concurrent sync/search safety with SQLite WAL, bounded busy waits, race tests,
  and post-race integrity checks
- A realistic-semester scale tier with 180 sources, 560 records, exact retrieval,
  and explicit index, incremental-sync, median-query, and p95-query thresholds
- WebVTT and SRT lecture transcripts with one record per cue, exact start/end
  milliseconds, timestamp citations, and verification across all evidence paths
- Unified claim, citation, source, coverage, and artifact verification with
  `verify-study`
- A multi-domain accuracy benchmark for retrieval, citations, synthesis,
  unanswerable questions, claim checking, and visual-review signaling
- Persistent local flashcard scheduling with source-version staleness and
  progress backup/restore
- Adaptive offline HTML decks with confidence-before-reveal, due/new queues,
  Again/Hard/Good/Easy scheduling, and CLI-compatible progress exchange
- Render-validated PDF and HTML delivery checks, atomic PDF creation,
  overwrite protection, structured renderer output, and dependency diagnostics
- Checked cited claims against the records they cite with `check-claims`
- Installed the complete Agent Skill from the published package with
  `classcorpus install-skill`
- Published to PyPI with OpenID Connect trusted publishing
- Zero-setup evaluation with `classcorpus demo`
- Diagnostics for a console script whose interpreter no longer exists
- Privacy-preserving artifact manifests and source-drift verification
- Exact evidence inspection with source freshness and local previews
- Remembered course lifecycle commands that preserve source folders
- DOCX extraction with explicit visual and equation review warnings
- Optional PDF study-guide rendering with human-readable mathematics
- Cursor-based course outline for token-efficient coverage planning
- Compact, budgeted retrieval by default with a lossless `--full` opt-out
- Query-centered focused reads and bounded, resumable evidence reads
- Explainable lexical reranking and local typo suggestions
- Self-contained adaptive HTML flashcard decks, plus CSV and TSV helpers
- A unified CLI with course status and environment diagnostics
- Isolated parser plugins for Markdown and plain-text lectures
- Optional local OCR with explicit, uncalibrated confidence reporting
- Sentence-transformers, FastEmbed, and dependency-free hashing backends
- Review tooling for layout-dependent PowerPoint records
- A published retrieval and extraction benchmark corpus
- Untrusted-content marking on every source-derived payload
