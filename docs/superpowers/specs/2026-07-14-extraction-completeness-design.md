# Extraction Completeness Hardening

## Goal

ClassCorpus must not silently truncate, omit, or overstate the completeness of
lecture extraction. It should preserve every character returned by native
parsers, account for every PDF page and PowerPoint slide, detect likely partial
extraction, and make uncertain records searchable with an explicit
`review-needed` status.

This design does not promise perfect interpretation of arbitrary scans,
diagrams, equations, damaged files, or unsupported document features. No
single parser, OCR engine, or model can make that guarantee. Instead,
ClassCorpus will distinguish verified facts from uncertainty and provide a
complete review path.

## Current Behavior

The current implementation has two separate behaviors:

- Parsing stores the complete `title`, `body_text`, and `speaker_notes` strings
  returned by the parser. SQLite `TEXT` fields do not impose an application
  character limit.
- Search intentionally returns at most eight records by default. Its `snippet`
  is abbreviated, but each returned record contains the full stored fields.

The current gap is detection. A record receives an `image_only` warning when
all native text fields are empty, but partial extraction can appear successful.
The skill also lacks a deterministic way to read every record in a requested
lecture without relying on search ranking.

## Chosen Approach

Use layered completeness verification:

1. Preserve lossless native parser output separately from normalized search
   fields.
2. Audit source structure and extraction evidence independently.
3. Mark uncertain records as `review-needed` without blocking indexing.
4. Provide ordered, paginated exhaustive retrieval for full-lecture tasks.
5. Prioritize uncertain records for opt-in visual review.

This provides stronger and more honest coverage than warnings alone, without
the privacy cost and latency of sending every slide to a vision model.

## Guarantees

For every successfully indexed source, ClassCorpus will guarantee:

- One stored record exists for every PDF page or PowerPoint slide.
- Ordinals are contiguous, one-based, and match the source count.
- Native parser output is stored without an application-level character limit.
- Normalization used for search does not overwrite the preserved native text.
- Every record has an extraction status and machine-readable reasons.
- Exhaustive retrieval can enumerate every stored ordinal exactly once.
- API payloads state whether more records remain; pagination is never implicit.
- Search limits affect the number of returned records, not the content fields
  inside each returned record.
- Indexing reports the number of records needing review.

ClassCorpus will not claim that `text-extracted` means all visual meaning was
captured. It means only that native text extraction passed the available
structural audits.

## Record Model

Extend each slide/page record with:

- `raw_text`: native text before search normalization or title splitting.
- `extraction_status`: `text-extracted`, `review-needed`, or
  `visually-reviewed`.
- `extraction_reasons`: ordered machine-readable reason codes.
- `native_text_chars`: the Unicode character count of `raw_text`.
- `has_visual_content`: whether the source record contains or renders
  non-textual content that may carry meaning.

The existing `title`, `body_text`, `speaker_notes`, `visual_description`, and
`render_path` fields remain. Full-text search continues to index normalized
fields plus visual descriptions.

Reason codes include:

- `no-native-text`
- `low-native-text`
- `native-extractor-disagreement`
- `embedded-image`
- `chart-or-diagram`
- `equation-or-embedded-object`
- `unmapped-ooxml-text`
- `renderer-unavailable`

Reasons indicate review risk, not proof that extraction failed.

## PDF Completeness Audit

For each PDF:

1. Open the document once and record its page count.
2. Produce exactly one record and one render attempt per page.
3. Preserve the native `text` extraction as `raw_text`.
4. Independently inspect word and block representations.
5. Mark the page `review-needed` when:
   - no native text is available;
   - text, word, and block representations materially disagree;
   - the page contains images with little native text; or
   - rendering fails.
6. Keep all successfully extracted text searchable even when review is needed.

The audit must use deterministic structural signals. It must not invent a
numeric confidence score that implies calibrated accuracy.

## PowerPoint Completeness Audit

For each PPTX:

1. Produce exactly one record per slide.
2. Preserve text frames, grouped shapes, tables, and speaker notes.
3. Read text runs from the underlying slide and notes OOXML as an independent
   census.
4. Compare the OOXML text census with the stored searchable fields.
5. Preserve any text found by the census that the higher-level parser did not
   map, and mark the record `review-needed` with
   `unmapped-ooxml-text`.
6. Detect images, charts, SmartArt/diagram relationships, equations, and
   embedded objects as visual-review signals.
7. Keep `renderer-unavailable` as a source warning because visual review is
   impossible without a render.

The OOXML census is a completeness backstop, not a replacement for structured
title, body, table, and notes extraction.

## Exhaustive Retrieval

Add an agent-facing script for ordered lecture reading. It accepts:

- required `--course`;
- optional `--source`;
- optional opaque `--cursor`;
- optional positive `--limit`.

The JSON response contains:

- `records`;
- `total_records`;
- `returned_records`;
- `has_more`;
- `next_cursor`;
- `review_needed`;
- `warnings`.

Records are ordered by source path and ordinal. `next_cursor` encodes both
values, even when one source is selected, so the continuation contract is
uniform and duplicate ordinals across files cannot skip data. The cursor is
treated as an opaque script-generated value by agents.

The command returns full stored fields. It never abbreviates `raw_text`,
`body_text`, `speaker_notes`, or `visual_description`.

Normal search remains ranked and limited because focused questions should not
load an entire semester. The skill uses exhaustive retrieval for summaries,
flashcards, exams, cheat sheets, comparisons, and any request whose scope says
"all," "every," or names a complete lecture range.

## Visual Review

`vision_queue.py` will prioritize `review-needed` records, followed by other
pending renders. Visual analysis remains opt-in because images are viewed under
the active agent's data policy.

Storing a visual description changes the record to `visually-reviewed` while
retaining its extraction reasons. This records that the image was inspected;
it does not erase evidence about native parser limitations.

The agent must describe diagrams, labels, equations, annotations, spatial
relationships, and conclusions. A plain transcription is not sufficient for
visual review.

## Index And Search Reporting

Index JSON adds:

- `records_indexed`;
- `records_review_needed`;
- warning entries with source path, ordinal, and reason.

Search and exhaustive-read records expose extraction status and reasons.
Search responses add a warning when any returned evidence needs review.

A partial or uncertain extraction remains usable. The agent must state the
coverage limitation when an answer depends on a `review-needed` record or when
an exhaustive task finishes with unreviewed records.

## Database Migration

Add nullable/defaulted columns through the existing schema initialization path
so existing indexes upgrade in place. Existing records receive:

- reconstructed `raw_text` from their stored title and body;
- `review-needed`;
- reason `legacy-record-not-audited`;
- the corresponding character count.

The parser version must increase so unchanged lecture files are reprocessed
under the new audit rules. Migration and reprocessing must preserve the current
transactional publication behavior: a failed refresh keeps the last searchable
records and marks them stale.

## Testing

All production changes follow test-driven development.

### Parser Tests

- PDF page count equals stored record count.
- PPTX slide count equals stored record count.
- Ordinals are contiguous and one-based.
- Long native text well beyond typical model context sizes is preserved as the
  exact Unicode string returned by the parser.
- Blank lines and meaningful whitespace remain in `raw_text`.
- Nested group text, tables, and notes are preserved.
- OOXML-only text is preserved and marked for review.
- Image-only and mixed image/text pages are marked for review.
- Charts, diagrams, equations, and embedded objects produce review reasons.
- Renderer failures are reported without discarding extracted text.

### Storage And Retrieval Tests

- Database round trips preserve complete raw and normalized fields.
- FTS snippets may be abbreviated while returned content fields remain full.
- Exhaustive pagination returns every record exactly once with no gaps or
  duplicates.
- `has_more` and continuation values are correct at page boundaries.
- Course-wide pagination handles identical ordinals from multiple files.
- Legacy schema migration is deterministic and non-destructive.

### Skill And Contract Tests

- A focused question uses ranked search.
- A whole-lecture request iterates exhaustive retrieval until `has_more` is
  false.
- An agent discloses remaining `review-needed` records.
- Visual review requires confirmation and prioritizes uncertain records.
- JSON contracts document all new status and pagination fields.

### Acceptance Tests

- Index the real LectureLens design PDF and account for every source page.
- Confirm total stored native characters are not reduced by retrieval.
- Re-index unchanged content and verify it is skipped.
- Run exhaustive retrieval and prove all ordinals are returned exactly once.
- Run a focused query and confirm exact citations remain unchanged.
- Complete one visual review and confirm status and reasons are preserved.

## Non-Goals

- Claiming perfect OCR or visual interpretation.
- Automatically sending every page to a model.
- Adding a hosted service, UI, server, or telemetry.
- Replacing exact citations with model-generated source labels.
- Removing ranked search or its intentional record limit.

## Acceptance Criteria

The work is complete when:

1. No parser or retrieval path applies an undocumented content truncation.
2. Every successful source has a complete page/slide ledger.
3. Suspected partial extraction is visible in records, warnings, and agent
   responses.
4. Full-scope tasks can deterministically enumerate all records.
5. Existing citations, incremental indexing, stale-record behavior, and privacy
   boundaries still pass their tests.
6. The real design PDF and generated adversarial fixtures pass the acceptance
   suite.
