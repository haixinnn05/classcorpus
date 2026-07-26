# Changelog

## Unreleased

### Added

- Build and smoke-test versioned Python distributions and a complete Agent
  Skill zip, then attach them automatically to future GitHub Releases.
- Prepare guarded PyPI trusted publishing with public package metadata and
  release setup documentation.

## 0.5.0 - 2026-07-24

### Added

- Inspect exact citation evidence, source freshness, extraction warnings, and
  local visual previews with `classcorpus inspect`.
- Manage remembered course folders with `classcorpus add`, `list`, `sync`, and
  guarded `remove` commands while preserving the legacy `index` command.
- Index DOCX paragraphs, hyperlinks, tables, and OOXML text as a cited logical
  document record, with explicit review warnings for images and equations.
- Mark every evidence-bearing agent payload as untrusted source content and
  instruct agents to ignore instructions embedded in lecture materials.
- Create privacy-preserving artifact provenance manifests and verify generated
  outputs against their cited indexed sources with `verify-artifact`.
- Write provenance sidecars automatically for PDF study guides and interactive
  HTML flashcard decks.

### Changed

- Automatically typeset standalone equations and inline math in PDF study
  guides, including stacked compact/LaTeX matrices, column vectors,
  determinant bars, fractions, Greek symbols, and common named functions.
- Center focused retrieval on matching evidence and reduce its default selected
  passage from 1,200 to 900 characters.

## 0.4.0 - 2026-07-15

### Added

- Generate self-contained interactive HTML flashcard decks from cited JSON,
  with reveal, navigation, shuffle, topic filters, session-only review
  tracking, responsive layout, and offline operation.
- Retrieve focused evidence in one deduplicated response with task-local cache
  keys, bounded selected text, ranked alternatives, citations, and extraction
  warnings.
- Benchmark focused retrieval end to end, including target-evidence coverage
  and context-efficiency gates.

### Changed

- Make cited JSON plus interactive HTML the default flashcard output; CSV and
  TSV remain optional interchange formats and plain text remains the fallback.
- Route narrow fact lookups through focused retrieval while preserving the
  existing compact search and bounded read commands for broader questions.

### Compatibility

- Existing JSON, CSV, TSV, search, read, outline, and full-search contracts
  remain supported.
- All rendering and retrieval remain local, provider-neutral, and free of
  telemetry or hosted services.
