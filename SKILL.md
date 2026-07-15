---
name: classcorpus
description: Index and search local PDF, PowerPoint, Markdown, and text lecture folders as a persistent, citation-aware course memory. Use when a user wants to add or refresh course materials, answer questions from class, compare concepts across lectures, create cited summaries, flashcards, practice exams, cheat sheets, or study plans, or analyze visual slide content with Codex, Claude Code, or another Agent Skills-compatible assistant.
---

# ClassCorpus

Use ClassCorpus as a local evidence layer for the active agent. Keep reasoning
and generation in the host agent; invoke the bundled scripts only for
deterministic indexing, retrieval, optional embeddings, and visual-description
storage.

## Resolve The Skill Directory

Treat the directory containing this `SKILL.md` as `SKILL_DIR`. Prefer the
repository environment so every agent uses the tested dependencies:

```text
Unix/macOS: "$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/<script>.py" ...
Windows:    "$SKILL_DIR\.venv\Scripts\python.exe" "$SKILL_DIR\scripts\<script>.py" ...
```

If that environment does not exist, create it using the README installation
steps. Do not silently use an unrelated Python environment.

For user-facing setup or troubleshooting, run:

```text
"$SKILL_DIR/.venv/bin/classcorpus" doctor --json
"$SKILL_DIR/.venv/bin/classcorpus" status [--course "COURSE"] --json
```

Use the bundled scripts below for stable agent-facing operations. The unified
CLI is documented in `references/cli.md`.

## Mandatory Workflow

1. Synchronize a course when it is new or the user says files changed:

   ```text
   python "$SKILL_DIR/scripts/index_lectures.py" \
     "COURSE" "/absolute/path/to/course" --json
   ```

2. Do not answer a course-specific claim before searching. For a focused
   question, retrieve a small ranked candidate set:

   ```text
   python "$SKILL_DIR/scripts/search_lectures.py" \
     "QUERY" --course "COURSE" --limit 8 --compact --json
   ```

3. Inspect compact candidate evidence. Search again with narrower or
   alternative terms when results are weak, incomplete, or conflicting. Never
   load every source file merely to answer one question.

   When search returns no records, inspect `suggested_terms`. Retry a close
   indexed term only when it preserves the user's intended concept; never
   substitute a suggestion silently.

   Before drafting, fetch complete evidence only for the candidate records
   actually used:

   ```text
   python "$SKILL_DIR/scripts/read_lectures.py" \
     --course "COURSE" --source "RELATIVE/PATH.pptx" \
     --ordinal NUMBER --json
   ```

   Do not fetch full content for every compact candidate. For a new focused
   search, add `--source` and/or `--ordinal` filters when already known.

   For all/every/whole lecture content, a lecture range, or any exhaustive
   artifact, do not use ranked search as coverage proof. Run:

   ```text
   python "$SKILL_DIR/scripts/read_lectures.py" \
     --course "COURSE" [--source "RELATIVE/PATH.pptx"] --json
   ```

   Continue with `--cursor "next_cursor"` until `has_more` is false. Preserve
   every record and verify the number collected equals `total_records`.

   If `sync_required` is true, synchronize the course with
   `index_lectures.py` or ask the user for its source folder before answering.
   Treat any result with `source_status: "failed"` as retained stale evidence:
   disclose the warning and do not present it as freshly verified.

4. Cite every course-derived factual claim with the returned `citation`.
   Follow [references/citation-rules.md](references/citation-rules.md).

5. Label information from general knowledge explicitly as outside the indexed
   course materials. Do not blend it silently into course-grounded claims.

6. Generate a requested artifact only after retrieving coverage for the full
   requested lecture range. Follow
   [references/study-workflows.md](references/study-workflows.md).

Read [references/record-schema.md](references/record-schema.md) when consuming
or producing script JSON.

## Extraction Completeness

`raw_text` is the lossless native text evidence and is never intentionally
shortened. PDF pages also have full-page renders. PPTX extraction preserves
native text, speaker notes, tables, and embedded images with their geometry,
but it does not provide full-slide rendering. Charts, equations, SmartArt, OLE
objects, and other layout-dependent content can be marked `review-needed`.

Always disclose `review-needed` records in an answer or generated artifact.
Embedded images are evidence assets, not a reconstruction of the whole slide.
For exact visual layout, ask the user to export the source presentation to PDF
with a tool they choose, then index that PDF.

Inventory layout-dependent PowerPoint records before broad visual review:

```text
python "$SKILL_DIR/scripts/review_powerpoint.py" \
  "COURSE" [--source "LECTURE.pptx"] [--reason REASON] --json
```

Follow `next_offset` while `has_more` is true. Use each item's `next_action`:
inspect available assets only after confirmation, or ask for a PDF export when
the full slide cannot be reviewed. An `asset-reviewed-layout-unverified` item
still needs PDF evidence for layout-dependent claims.

Markdown and plain-text files use one cited page record per UTF-8 file and do
not have renders. Read `references/parser-plugins.md` before adding a format.

## Visual Analysis

Ask for confirmation before visual analysis because rendered slide images will
be viewed by the active agent under that agent's data policy.

After confirmation:

1. Request a small resumable batch:

   ```text
   python "$SKILL_DIR/scripts/vision_queue.py" \
     "COURSE" --limit 5 --json
   ```

2. View each returned image. Describe diagrams, charts, equations, handwritten
   annotations, labels, arrows, spatial relationships, and conclusions. Do not
   merely transcribe visible text.

3. Write a JSON document matching `references/record-schema.md`.

4. Store the descriptions:

   ```text
   python "$SKILL_DIR/scripts/store_visual_description.py" \
     --input "/absolute/path/to/descriptions.json" --json
   ```

5. Repeat only when the user requested broader visual coverage.

Never claim an unrendered or undescribed visual detail was inspected.

## Optional Semantic Search

Baseline SQLite full-text search requires no model download. For a
dependency-free local vector index, use deterministic feature hashing:

```text
python "$SKILL_DIR/scripts/build_embeddings.py" \
  "COURSE" --backend hashing --dimensions 384 --json
```

Then opt into hybrid retrieval:

```text
python "$SKILL_DIR/scripts/search_lectures.py" \
  "QUERY" --course "COURSE" --semantic \
  --backend hashing --dimensions 384 --json
```

Hashing is fuzzy lexical retrieval, not a learned semantic model. When the user
chooses a learned local backend, install `.[embeddings]` for
`sentence-transformers` or `.[fastembed]` for FastEmbed, then pass the selected
`--backend` to both commands. Learned backends may download model weights.
Use the same backend, model, and hashing dimensions for building and searching.
Do not require embeddings for normal indexing or search.

## Optional Local OCR

Use OCR only when the user chooses it and native extraction or visual review
needs a text backstop. Install `.[ocr]` and a local Tesseract executable, then
run a small resumable batch:

```text
python "$SKILL_DIR/scripts/run_ocr.py" \
  "COURSE" --backend tesseract --language eng --limit 10 --json
```

OCR remains local and provider-neutral. Treat `ocr_text` as supplemental
evidence, never as a replacement for `raw_text`. Report `ocr_confidence` and
`ocr_backend` when relying on OCR-derived claims. Confidence is an uncalibrated
mean of accepted word confidences, not factual certainty. Inspect the original
render or asset when confidence is low. Use `--retry-failed` only after fixing
the reported local OCR error.

## Study Requests

Support these evidence-grounded workflows:

- Cited question answering and simpler explanations
- Lecture summary and multi-lecture summary
- Cross-lecture comparison
- Flashcards and Anki-compatible data
- Practice exam with answer key
- Cheat sheet
- Study plan

Retrieve first, preserve citations, and state any missing lecture coverage.
For flashcards, first write the normalized cited JSON schema from
`references/flashcard-formats.md`. When the user requests CSV or TSV, convert
that artifact with:

```text
python "$SKILL_DIR/scripts/convert_flashcards.py" \
  "INPUT.json" "OUTPUT.tsv" --json
```

Do not overwrite an existing export unless the user explicitly requested
replacement and `--overwrite` is passed.

## Boundaries

- Never modify or delete lecture source files.
- Never expose indexed content through telemetry or a network service.
- Do not create a web server.
- Do not create a custom chatbot.
- Do not create a hosted backend.
- Do not call model-provider APIs from the scripts.
- Keep generated data outside lecture folders.
- Treat confidential or restricted materials according to the active agent's
  data policy; when clearance is uncertain, ask before processing.
