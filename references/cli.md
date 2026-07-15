# Unified CLI

The installed `classcorpus` command is the human-facing entry point. Existing
scripts remain stable agent-facing JSON contracts.

## Core Commands

```text
classcorpus index COURSE SOURCE_ROOT [--json]
classcorpus search QUERY [--course COURSE] [--source PATH] \
  [--ordinal N] [--limit N] [--semantic] [--backend BACKEND] \
  [--budget-tokens N] [--full] [--compact] [--json]
classcorpus read COURSE SOURCE ORDINAL [--field FIELD] \
  [--offset N] [--limit N] [--json]
classcorpus outline COURSE [--source PATH] [--cursor CURSOR] \
  [--budget-tokens N] [--json]
classcorpus status [--course COURSE] [--json]
classcorpus doctor [--json]
```

`index` and `search` preserve the behavior and fields of their corresponding
scripts. Without `--json`, the CLI prints compact output intended for a person.
With `--json`, success payloads contain `"ok": true`, and failures exit nonzero
with a structured error.

Focused search retrieves a wider FTS candidate set, then reranks it using query
term coverage, exact phrase presence, and title matches. When no record
matches, close indexed vocabulary is shown as a suggestion without changing or
rerunning the user's query automatically.

Search uses compact output by default for agent or automation candidate
selection. It returns at most six results within a 1,200 estimated-token budget
and reports `estimated_tokens`, `budget_tokens`, and `budget_exhausted`.
Repeated source metadata lives in the response-level `sources` map.

`--compact` is a deprecated no-op. Use `--full` for complete record bodies.
Fetch a bounded chunk from only the chosen record with
`read_record.py --source PATH --ordinal N --json`, then follow `next_offset`
only when more text is needed. This two-stage flow keeps full evidence
available while avoiding repeated large-record payloads.

## Read

`read` exposes the bounded record reader through the installed CLI. It returns
at most 2,000 characters by default and accepts up to 50,000. Select
`searchable`, `raw_text`, `body_text`, `speaker_notes`, `visual_description`,
or `ocr_text` with `--field`.

JSON output follows the `scripts/read_record.py` contract, including citation,
extraction status, total and returned character counts, `has_more`, and
`next_offset`. Human output prints the evidence and an exact continuation
command only when more text remains.

## Outline

`outline` returns an ordered coverage ledger without full record bodies.
Consecutive records from one source with matching normalized titles are grouped
into exact ordinal ranges. Every slide/page is represented once through
`start_ordinal`, `end_ordinal`, and `record_count`.

The default budget is 1,500 estimated tokens. Follow `next_cursor` until
`has_more` is false, then read only selected ranges. Citations, warnings,
coverage markers, extraction review counts, and continuation are never
truncated.

## Status

`status` reports every indexed course or one selected course:

- source totals and ready/failed refresh state;
- total, review-needed, and visually reviewed records;
- pending, complete, and failed OCR counts;
- embedded record count and stored embedding model identities;
- concrete next actions for failed refreshes, review work, or OCR failures.

An unknown course is not an operational error. It returns an empty course list
and the exact `classcorpus index` command to start.

## Doctor

`doctor` performs no network requests. Required checks are:

- Python 3.11 or newer;
- SQLite FTS5;
- writable generated-data directory;
- initializable ClassCorpus database.

Sentence-transformers, FastEmbed, the Python OCR adapter, and the Tesseract
executable are optional checks. Their absence is reported with installation
guidance but does not fail the command. A required failure makes `ok` false and
the process exits nonzero.
