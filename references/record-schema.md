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
complete summary while preserving successfully indexed files. A PPTX indexed
without images reports how to install LibreOffice. Image-only records use
warning type `image_only`; non-fatal cache cleanup failures use
`cache_cleanup_failed`.

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

## Vision Queue

```text
python scripts/vision_queue.py COURSE [--limit N] --json
```

Returns rendered records that do not yet have visual descriptions.

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
python scripts/build_embeddings.py COURSE [--model MODEL] --json
```

This command requires the `embeddings` optional dependency group. Baseline
indexing and full-text search never require a model download.

Pass `--semantic` and the same optional `--model` value to
`search_lectures.py` to combine stored vectors with FTS results.

## Remove Course Data

```text
python scripts/remove_course.py COURSE --confirm --json
```

Returns `removed: true` when generated records existed. Omitting `--confirm`
returns a JSON error and leaves all generated and source data unchanged.
If cache deletion is interrupted after confirmed removal, the command keeps a
local pending-deletion manifest; rerun the confirmed command to finish cleanup.
