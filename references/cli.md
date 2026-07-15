# Unified CLI

The installed `classcorpus` command is the human-facing entry point. Existing
scripts remain stable agent-facing JSON contracts.

## Core Commands

```text
classcorpus index COURSE SOURCE_ROOT [--json]
classcorpus search QUERY [--course COURSE] [--source PATH] \
  [--ordinal N] [--limit N] [--semantic] [--backend BACKEND] [--json]
classcorpus status [--course COURSE] [--json]
classcorpus doctor [--json]
```

`index` and `search` preserve the behavior and fields of their corresponding
scripts. Without `--json`, the CLI prints compact output intended for a person.
With `--json`, success payloads contain `"ok": true`, and failures exit nonzero
with a structured error.

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

