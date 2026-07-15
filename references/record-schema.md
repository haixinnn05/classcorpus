# Script JSON Contracts

All commands support `--json`. Successful payloads contain `"ok": true`.
Operational failures exit with status 1 and return:

```json
{
  "ok": false,
  "error": {
    "type": "ValueError",
    "message": "limit must be at least 1"
  }
}
```

## Index

```text
python scripts/index_lectures.py COURSE SOURCE_ROOT --json
```

Returns `indexed`, `skipped`, `failed`, `failures`, and actionable `warnings`.
A partial sync exits 1 with `ok: false`, error type `PartialSyncError`, and the
complete summary while preserving successfully indexed files. PPTX files
retain native text and embedded image assets but do not produce a full-slide
render. Layout-dependent records use `review-needed`; records with no viewable
evidence may report `visual-source-unavailable`. Non-fatal cache cleanup
failures use `cache_cleanup_failed`.

## Search

```text
python scripts/search_lectures.py QUERY [--course COURSE] \
  [--source RELATIVE_PATH] [--ordinal N] [--limit N] --json
```

Each result contains course, source file and absolute path, one-based ordinal,
kind (`slide` or `page`), extracted content, render path, vision status,
`source_status`, optional `source_error`, score, and a ready-to-use `citation`.

The response also contains `warnings` and `sync_required`. Synchronization is
required when the requested course has no indexed sources or a source's latest
refresh failed. Retained evidence from a failed refresh remains available with
`source_status: "failed"` and a `source_failed` warning so the agent can disclose
that it may be stale. An indexed query with no match sets `sync_required: false`
and suggests alternative terms or filters.

`--source` matches the source path relative to the indexed course root.
`--ordinal` limits results to one one-based slide or page number.

Argument-validation failures also use the JSON error envelope and exit 1 when
`--json` is present.

## Exhaustive Read

```text
python scripts/read_lectures.py --course COURSE \
  [--source RELATIVE_PATH] [--cursor CURSOR] [--limit N] --json
```

Use this command for whole lectures, ranges, and all/every/full-scope study
artifacts. Records are ordered by source path and one-based ordinal. The
response contains `records`, `total_records`, `returned_records`, `has_more`,
opaque `next_cursor`, scope-wide `review_needed`, and `warnings`.

Each record includes source status/error, title, body, notes, complete
`raw_text`, extraction status/reasons, native character count, visual
description, OCR text/backend/confidence/status, render path, `visual_assets`,
and canonical `citation`. Each
visual asset includes its exact generated path, content type, shape name, kind,
and PowerPoint EMU geometry (`left`, `top`, `width`, `height`).

## Vision Queue

```text
python scripts/vision_queue.py COURSE [--limit N] --json
```

Returns viewable records that do not yet have visual descriptions. PDF records
provide full-page renders; PPTX records may provide embedded image assets.

## PowerPoint Review Report

```text
python scripts/review_powerpoint.py COURSE [--source RELATIVE_PATH] \
  [--reason REASON] [--unreviewed-only] [--limit N] [--offset N] --json
```

Returns every layout-dependent PPTX record matching the filters. The summary
contains `total_matches`, `returned_items`, `has_more`, `next_offset`,
`by_reason`, and `by_state`; counts cover the full filtered result, not only the
current page.

Each item contains exact source metadata, extraction evidence, citation,
available assets, `review_state`, and `next_action`. States are:

- `full-render-available`: inspect the complete render.
- `asset-review-available`: embedded assets can be inspected, but slide layout
  remains unverified.
- `asset-reviewed-layout-unverified`: assets were described; export to PDF for
  layout-dependent claims.
- `pdf-export-required`: no viewable evidence is available.

Valid reason filters are `embedded-image`, `chart-or-diagram`,
`equation-or-embedded-object`, and `unmapped-ooxml-text`.

## Store Visual Descriptions

```text
python scripts/store_visual_description.py --input descriptions.json --json
```

The input document is:

```json
{
  "descriptions": [
    {
      "slide_id": 1,
      "description": "A directed graph with negative weighted edges."
    }
  ]
}
```

Descriptions must contain at least 10 characters. Storage is atomic.

## Optional Embeddings

```text
python scripts/build_embeddings.py COURSE \
  [--backend sentence-transformers|fastembed|hashing] \
  [--model MODEL] [--dimensions N] --json
```

The default `sentence-transformers` backend requires the `embeddings` optional
dependency group. FastEmbed requires the `fastembed` group. The `hashing`
backend is built in, accepts `--dimensions` instead of `--model`, and requires
no dependency or model download.

Pass `--semantic` and the same backend configuration to `search_lectures.py`
to combine stored vectors with FTS results. The build response returns the
effective `backend` and stored `model` identity. Baseline indexing and
full-text search never require embeddings.

## Optional Local OCR

```text
python scripts/run_ocr.py COURSE [--backend tesseract] \
  [--language LANGUAGE] [--limit N] [--retry-failed] --json
```

The command processes queued PDF renders or PPTX embedded assets locally.
Successful results contain `text`, `confidence`, and `backend`; the same values
become visible as `ocr_text`, `ocr_confidence`, `ocr_backend`, and `ocr_status`
in search and exhaustive-read records. OCR text is indexed by FTS and changes
invalidate stale slide embeddings.

Confidence is constrained to `0` through `1` and is the mean accepted
Tesseract word confidence, not calibrated certainty. Per-record failures are
isolated, marked `failed`, and returned with a `PartialOCRFailure` envelope.
Use `--retry-failed` after correcting the local dependency or image error.

## Remove Course Data

```text
python scripts/remove_course.py COURSE --confirm --json
```

Returns `removed: true` when generated records existed. Omitting `--confirm`
returns a JSON error and leaves all generated and source data unchanged.
If cache deletion is interrupted after confirmed removal, the command keeps a
local pending-deletion manifest; rerun the confirmed command to finish cleanup.
