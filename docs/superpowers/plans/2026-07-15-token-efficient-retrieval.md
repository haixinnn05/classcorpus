# Token-Efficient Retrieval Implementation Plan

**Design:** `docs/superpowers/specs/2026-07-15-token-efficient-retrieval-design.md`

## 1. Response Budgeting

- Add deterministic JSON token estimation to `payloads.py`.
- Serialize compact search results with response-level source metadata.
- Apply evidence-only trimming after required metadata is assembled.
- Keep complete serialization behind `--full`.
- Add unit tests for estimates, deduplication, required fields, and size
  reductions.

## 2. Search And Read Interfaces

- Make compact output the CLI and script default.
- Add `--full` and `--budget-tokens`; retain `--compact`.
- Cap normal focused output at six ranked candidates.
- Lower bounded-read defaults to 2,000 characters.
- Update human output and JSON contract tests.

## 3. Coverage Ledger

- Add `classcorpus.outline` with normalized-title grouping and opaque cursors.
- Guarantee ordered, gap-free, duplicate-free page coverage.
- Add `classcorpus outline` and `scripts/outline_lectures.py`.
- Add grouping, budget, continuation, warning, and malformed-cursor tests.

## 4. Skill And Documentation

- Reduce `SKILL.md` to at most 650 words and less than 6 KB.
- Route extraction, OCR, embeddings, visual review, formats, and study details
  to existing references.
- Document v0.3 migration and progressive retrieval contracts.
- Update package version and CLI references.

## 5. Validation

- Run focused tests during implementation.
- Run full pytest and Ruff.
- Run the reproducible benchmark and verify recall@5 and MRR are 1.0.
- Run the skill validator.
- Measure payload reductions against full search and exhaustive record JSON.
- Review the final diff and create one local milestone commit.
