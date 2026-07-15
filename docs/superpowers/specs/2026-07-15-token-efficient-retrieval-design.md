# Token-Efficient Retrieval Design

**Date:** 2026-07-15
**Target release:** 0.3.0

## Goal

Reduce the agent context required for focused search and whole-course planning
without losing citations, extraction warnings, ranking evidence, or exact page
coverage. Stored records and the Python `search()` API remain lossless.

## Progressive Evidence Protocol

ClassCorpus returns the smallest useful planning payload first, then exposes
deterministic selectors for reading only the chosen evidence.

1. `search` returns compact ranked candidates by default.
2. `read` returns a bounded text chunk from one selected record.
3. `outline` returns a coverage ledger for exhaustive planning.
4. Existing exhaustive readers remain available when complete record bodies
   are explicitly required.

`--full` restores the pre-0.3 complete search result payload. The old
`--compact` option remains accepted as a deprecated no-op.

## Token Budgets

Token counts are deterministic estimates: compact JSON character count divided
by four, rounded up. They are planning estimates, not provider billing counts.

Focused search defaults to a 1,200-token response budget and at most six ranked
results. Outline defaults to 1,500 tokens. Both accept `--budget-tokens`.

Every budgeted response reports:

- `estimated_tokens`
- `budget_tokens`
- `budget_exhausted`
- continuation data when more evidence or coverage is available

Budgets trim or omit evidence text before structural metadata. Citations,
warnings, extraction state, rankings, source identity, and coverage markers
are never truncated. A response may exceed its requested budget when mandatory
metadata alone is larger than the budget; `budget_exhausted` makes that
explicit.

## Search Contract

Compact results contain ranked metadata, bounded query-centered evidence, a
canonical citation, and a selector for `classcorpus read`. Repeated source
path, health, and error fields move into a response-level `sources` map.

`--full` returns all fields from `SearchResult`, including complete record
text, visual descriptions, render paths, and visual assets. Internal callers
of `search()` see no behavior change.

Typo suggestions remain advisory and are never applied automatically.

## Bounded Read Contract

The default text chunk decreases from 8,000 to 2,000 characters. The 50,000
character maximum and lossless `offset`/`next_offset` continuation remain
unchanged. Citation, extraction state, source health, and character counts are
always returned.

## Coverage Ledger

`classcorpus outline COURSE` and `scripts/outline_lectures.py` emit every
indexed slide/page exactly once as ordered coverage ranges. Consecutive records
from the same source with the same normalized title and kind are grouped.
Source boundaries are never crossed.

Each range contains source identity, start and end ordinals, record count,
kind, title, review count, native text size, endpoint citations, and selectors
for expanding that range. A cursor points to the last represented record.
Following cursors until `has_more` is false must produce exactly
`total_records` records with no gaps or duplicates.

Warnings cover the entire requested scope and are emitted before optional
descriptive text. A single range is returned even when its required metadata
exceeds the budget, guaranteeing progress.

## Compatibility And Migration

- Package version becomes 0.3.0.
- `classcorpus search` and `search_lectures.py` become compact by default.
- `--compact` remains valid and has no behavioral effect.
- `--full` opts into the legacy complete payload.
- `search()` remains lossless for Python integrations.
- Existing exhaustive record readers remain supported.
- Documentation directs agents to `outline` for coverage planning and bounded
  `read` calls for selected evidence.

## Errors

Non-positive budgets, limits, ordinals, and malformed cursors use the existing
structured error envelope. Cursor validation rejects unknown fields and
invalid record positions. Missing courses return an empty, complete ledger
rather than fabricating coverage.

## Validation

Tests cover default compact search, `--full`, deprecated `--compact`,
source-level deduplication, budget metadata, evidence-first trimming, bounded
read defaults, outline grouping, cursor continuity, exact coverage, malformed
cursors, warnings, and skill size.

Acceptance targets:

- At least 60% smaller normal focused payloads.
- At least 80% smaller oversized-record payloads.
- At least 60% smaller whole-course planning input.
- Exact page coverage unchanged.
- Benchmark recall@5 and MRR remain 1.0.
- Full pytest, Ruff, skill validation, and benchmark pass.
