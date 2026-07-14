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

Returns `indexed`, `skipped`, `failed`, and `failures`. A partial sync exits 1
while preserving successfully indexed files.

## Search

```text
python scripts/search_lectures.py QUERY [--course COURSE] [--limit N] --json
```

Each result contains course, source file and absolute path, one-based ordinal,
kind (`slide` or `page`), extracted content, render path, vision status, score,
and a ready-to-use `citation`.

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

## Remove Course Data

```text
python scripts/remove_course.py COURSE --confirm --json
```

Returns `removed: true` when generated records existed. Omitting `--confirm`
returns a JSON error and leaves all generated and source data unchanged.
