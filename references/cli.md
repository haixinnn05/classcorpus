# Unified CLI

The installed `classcorpus` command is the human-facing entry point. Existing
scripts remain stable agent-facing JSON contracts.

`python -m classcorpus` accepts identical arguments. Prefer it when a moved or
renamed environment has broken the generated console script.

## Core Commands

```text
classcorpus demo [--course COURSE] [--dir PATH] [--query QUERY] \
  [--overwrite] [--json]
classcorpus add COURSE SOURCE_ROOT [--json]
classcorpus list [--json]
classcorpus sync COURSE [--json]
classcorpus remove COURSE --confirm [--json]
classcorpus index COURSE SOURCE_ROOT [--json]
classcorpus search QUERY [--course COURSE] [--source PATH] \
  [--ordinal N] [--limit N] [--semantic] [--backend BACKEND] \
  [--budget-tokens N] [--full] [--compact] [--json]
classcorpus read COURSE SOURCE ORDINAL [--field FIELD] \
  [--offset N] [--limit N] [--json]
classcorpus inspect COURSE SOURCE ORDINAL [--field FIELD] \
  [--offset N] [--limit N] [--json]
classcorpus manifest ARTIFACT --citations-from INPUT \
  [--overwrite] [--json]
classcorpus verify-artifact ARTIFACT [--json]
classcorpus outline COURSE [--source PATH] [--cursor CURSOR] \
  [--budget-tokens N] [--json]
classcorpus status [--course COURSE] [--json]
classcorpus doctor [--json]
```

## Demo

`demo` generates a small synthetic course from code, indexes it, and runs one
search, so ClassCorpus can be evaluated without any course files. It needs no
network access and no model download.

Generated files default to a `demo-course` folder inside the generated-data
directory, never inside a lecture folder. `--dir` selects another location.
`demo` refuses to write into an existing non-empty directory that it did not
generate unless `--overwrite` is explicit, so it cannot overwrite real course
material. Re-running it is safe.

JSON output reports `generated_files`, the `sync` report, the `query`, a standard
compact `search` payload, and `next_steps`.

`classcorpus remove "ClassCorpus Demo" --confirm` deletes the demo index. The
generated files stay on disk, because `remove` never deletes a course source
folder; delete the reported `source_root` to remove them.

## Course Lifecycle

`add` indexes a folder and remembers its canonical path. `sync` refreshes a
remembered course without requiring the path again. `list` reports every
course and its current health. `remove --confirm` deletes only generated index,
render, OCR, and embedding data; it never modifies source course files.

`index` remains a compatibility alias for `add`. Both preserve the agent-facing
`index_lectures.py` report fields and add `course` and `source_root`. Without
`--json`, commands print compact human output. With `--json`, success payloads
contain `"ok": true`, and failures exit nonzero with a structured error.

Evidence-bearing payloads also contain `content_trust: "untrusted"` and a fixed
`content_handling` rule. Apply that rule to every source-derived field,
including filenames and titles. See [security.md](security.md).

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

For a narrow fact, term, or named-concept lookup, agents may begin with
`--limit 3 --budget-tokens 600` and read the selected record with
`--limit 1200`. Use the balanced defaults for ambiguous, comparative, or
multi-concept questions, and fall back to them when ranking signals are weak
or the first read is insufficient. The published synthetic benchmark requires
this adaptive first pass to save at least 25% with unchanged retrieval quality.

## Read

`read` exposes the bounded record reader through the installed CLI. It returns
at most 2,000 characters by default and accepts up to 50,000. Select
`searchable`, `raw_text`, `body_text`, `speaker_notes`, `visual_description`,
or `ocr_text` with `--field`.

JSON output follows the `scripts/read_record.py` contract, including citation,
extraction status, total and returned character counts, `has_more`, and
`next_offset`. Human output prints the evidence and an exact continuation
command only when more text remains.

## Retrieve

`classcorpus retrieve QUERY --course COURSE --json` combines three ranked
candidates and a query-centered, 900-character read of the top result. The
window moves to later matching evidence and reports `offset`, `has_previous`,
and `previous_offset`. The selected passage
appears once; alternatives keep citations and ranking signals without
duplicate snippets or absolute paths. Reuse an identical `cache_key` only
within the current task.

## Inspect

`inspect` returns bounded evidence for one exact page or slide and verifies the
current source against its indexed SHA-256 and parser version. It reports
`current`, `changed`, `missing`, `stale-parser`, or `unavailable`, plus the
original path, extraction warnings, render availability, embedded visual
assets, and a continuation command.

Inspection is read-only. When evidence is stale, run `classcorpus sync COURSE`
before relying on it. JSON output is marked as untrusted source content.

## Artifact Provenance

`manifest` writes `ARTIFACT.classcorpus.json` beside a generated file. It
hashes the artifact and citation-bearing input, extracts canonical citations,
and records the indexed source hash and parser version for every resolved
source. Absolute local source paths are never stored in the manifest.

Use `--citations-from` with the cited Markdown or flashcard JSON used to create
the artifact. Existing manifests require `--overwrite`. The study-guide PDF
and flashcard HTML renderers create or update their sidecars automatically.

`verify-artifact` compares the current artifact and cited course files with
their stored hashes. JSON statuses are `current`, `artifact-modified`,
`artifact-missing`, `source-changed`, `source-missing`, or `unverified`.
Missing manifests are command errors. Unresolved citations create a manifest
but make verification `unverified`; fix the citation or synchronize the course
before treating it as current.

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
and the exact `classcorpus add` command to start.

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

The console entry point is also checked but is not required. Moving or renaming
an environment leaves the generated `classcorpus` script pointing at an
interpreter that no longer exists, which fails before any ClassCorpus code runs.
Both generated script forms are inspected: a direct shebang, and the `/bin/sh`
trampoline used when the interpreter path contains a space. A broken script is
reported as `fail` with repair instructions, and `python -m classcorpus`
continues to work in the meantime.
