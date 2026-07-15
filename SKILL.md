---
name: classcorpus
description: Index and search local PDF, PowerPoint, Markdown, and text lectures as persistent, citation-aware course memory. Use for class questions, summaries, comparisons, flashcards, practice exams, cheat sheets, study plans, visual slide analysis, or cited study guides.
---

# ClassCorpus

Use ClassCorpus as the local evidence layer. Let the host agent reason and
write; use bundled commands for deterministic indexing and retrieval.

## Setup

Treat this file's directory as `SKILL_DIR`. Use its tested environment:

```text
Unix/macOS: "$SKILL_DIR/.venv/bin/python" "$SKILL_DIR/scripts/SCRIPT.py"
Windows:    "$SKILL_DIR\.venv\Scripts\python.exe" "$SKILL_DIR\scripts\SCRIPT.py"
```

If missing, follow the README installation steps. Diagnose with
`.venv/bin/classcorpus doctor --json`; inspect coverage with
`.venv/bin/classcorpus status --course "COURSE" --json`. See
[references/cli.md](references/cli.md) for the unified CLI.

## Evidence Workflow

1. Synchronize new or changed material:

   ```text
   python "$SKILL_DIR/scripts/index_lectures.py" \
     "COURSE" "/absolute/course/path" --json
   ```

2. Do not answer a course-specific claim before searching:

   ```text
   python "$SKILL_DIR/scripts/search_lectures.py" \
     "QUERY" --course "COURSE" --json
   ```

   Search is compact by default, capped at six candidates, and budgeted to
   1,200 estimated tokens. `--compact` remains a deprecated no-op; use
   `--full` only when complete search records are explicitly necessary.
   Check ranking signals, warnings, and `suggested_terms`; never substitute a suggestion silently.

3. Read only selected evidence:

   ```text
   python "$SKILL_DIR/scripts/read_record.py" \
     --course "COURSE" --source "PATH" --ordinal NUMBER --json
   ```

   Follow `next_offset` only when needed.
   Do not fetch full content for every compact candidate.

4. For an all/every/whole-course or multi-lecture artifact, plan exact coverage:

   ```text
   python "$SKILL_DIR/scripts/outline_lectures.py" \
     --course "COURSE" --json
   ```

   Follow `next_cursor` while `has_more` is true, then expand only selected
   ranges. Use `read_lectures.py` when complete records are required. Verify
   represented records equal `total_records`; ranked search is not coverage
   proof.

5. Cite every course-derived factual claim. Follow
   [references/citation-rules.md](references/citation-rules.md). Label general
   knowledge as outside the indexed materials.

## Completeness

Disclose `review-needed` evidence and stale `source_status: failed` results.
PDFs have page renders. PPTX extraction preserves text, notes, tables, and
embedded images but lacks pixel-accurate full-slide rendering. Use
`review_powerpoint.py`, follow `next_offset`, and request a PDF export when
layout matters. Never claim an uninspected visual detail.

Ask for confirmation before visual analysis. Then use `vision_queue.py`, inspect
the returned images, and save descriptions with
`store_visual_description.py`. See
[references/record-schema.md](references/record-schema.md).

## Optional Features

- OCR: read the OCR section in the record schema before `run_ocr.py`. Keep
  `ocr_confidence` and backend visible; confidence is uncalibrated.
- Embeddings: read [references/cli.md](references/cli.md). Baseline FTS needs no
  model download.
- Formats: read [references/parser-plugins.md](references/parser-plugins.md)
  before adding PDF, PPTX, Markdown, or plain-text behavior.

## Study Outputs

For a summary, cross-lecture comparison, flashcards, practice exam, cheat
sheet, or study plan, retrieve requested coverage first and follow
[references/study-workflows.md](references/study-workflows.md). Use
`convert_flashcards.py`; never pass `--overwrite` without explicit permission.

For Markdown or PDF guides, write equations in fenced `math` blocks.
Never present equations as programming code. Render with
`scripts/render_study_guide.py SOURCE.md OUTPUT.pdf` and visually inspect the
PDF.

## Boundaries

Never modify lecture sources, expose indexed content through telemetry, or call
model-provider APIs.
Do not create a web server.
Do not create a custom chatbot.
Do not create a hosted backend.
Keep generated data outside lecture folders and follow the active agent's data
policy.
