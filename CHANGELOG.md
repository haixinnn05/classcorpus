# Changelog

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
