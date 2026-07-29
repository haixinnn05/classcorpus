# Roadmap

ClassCorpus prioritizes verifiable extraction and citations over adding an
application surface. It will remain an Agent Skill and local library: a hosted
service, custom chatbot, and required provider API are out of scope.

This roadmap lists work that is wanted but not yet done. Items are not promises,
and the order can change. If you want to take one on, open an issue first so the
approach can be agreed before code is written. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Distribution

- **Publish a Claude Code plugin manifest** so the skill is installable from the
  plugin marketplace.
- **Support more agents in `install-skill`.** Only Claude Code and Codex skill
  directories are known. Adding an agent should require one table entry.

## Formats

- **Lecture recording transcripts.** Parse WebVTT and SRT with timestamp-based
  citations, for example `[Algorithms, Lecture08.vtt, 14:32]`. Recordings hold a
  large share of current course material and fit the existing `ParserPlugin`
  contract.
- **HTML and EPUB** for online textbooks and course sites.

## Study Outputs

- **Persistent spaced repetition.** Flashcard review state is session-only.
  Store review history locally and export to Anki.
- **Deep-linked citations** that open the cited source at the exact page from
  generated HTML and PDF artifacts.

## Engineering

- **Measure subprocess coverage.** CLI tests run through `subprocess`, so
  `cli.py` reports no coverage even though it is exercised. Use parallel-mode
  coverage with a subprocess hook, then gate on the corrected total.
- **Ship type information.** Modules are annotated, but there is no `py.typed`
  marker, so library consumers get nothing. Add the marker and check with a
  static type checker in CI.
- **Widen lint coverage** beyond the current pycodestyle and pyflakes subset,
  and check formatting.
- **Close CI gaps.** Test Python 3.13, which the package classifiers claim.
  Run the benchmark in CI, which `CONTRIBUTING.md` requires before every change.
  Add a cold-install smoke test on every supported operating system.
- **Test concurrent access.** Agents can synchronize and search the same SQLite
  database at once; there is no locking or concurrency test.
- **Add a scale benchmark.** The published corpus is small. Add a
  realistic-semester tier with index-time and query-latency thresholds.

## Under Consideration

- **A local stdio MCP server** wrapping the existing retrieval contracts, so
  ClassCorpus works in editors and assistants that speak MCP rather than Agent
  Skills. This would not add a web server, hosted backend, or provider API, but
  it does widen the project's surface, so it needs a decision before work
  starts.

## Completed

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
- Self-contained interactive HTML flashcard decks, plus CSV and TSV helpers
- A unified CLI with course status and environment diagnostics
- Isolated parser plugins for Markdown and plain-text lectures
- Optional local OCR with explicit, uncalibrated confidence reporting
- Sentence-transformers, FastEmbed, and dependency-free hashing backends
- Review tooling for layout-dependent PowerPoint records
- A published retrieval and extraction benchmark corpus
- Untrusted-content marking on every source-derived payload
