# ClassCorpus Benchmarks

ClassCorpus publishes a deterministic, redistributable benchmark for native
lecture extraction, baseline SQLite FTS5 retrieval, and end-to-end agent
context efficiency. The corpus is generated from code, contains no private
course material, and requires no network access or model download.

## Run

From the repository environment:

```bash
.venv/bin/python -m benchmarks.run
.venv/bin/python -m benchmarks.scale
```

Use `--json` for the stable machine-readable result. To inspect the generated
PDF, PPTX, SQLite database, renders, and assets, keep one run:

```bash
.venv/bin/python -m benchmarks.run \
  --work-dir /tmp/classcorpus-benchmark --json
```

Generate only the source corpus with:

```bash
.venv/bin/python -m benchmarks.generate \
  --output /tmp/classcorpus-corpus
```

## Corpus

Version 4 contains:

- A two-page PDF with very long native text and a mixed text/image page.
- A six-slide PPTX covering nested groups, notes, tables, repeated embedded
  images, OOXML fallback text, a chart, an Office Math equation, DrawingML
  SmartArt, and an OLE object.
- Markdown and plain-text distractors that repeat partial query terms. These
  prove that full multi-term coverage outranks raw repetition.
- Thirty generated Markdown records with shared course vocabulary and unique
  target markers for focused token-efficiency queries.
- Ten original, redistributable sources across Physics, History, and Biology.
  They exercise equation-heavy, prose-heavy, and visual-review workflows,
  including a revised result that contradicts an earlier pilot estimate.

[`manifest.json`](manifest.json) is the benchmark contract. It records source
and record counts, exact extraction statuses/reasons, and expected retrieval
targets. Add or version expectations whenever parser behavior changes.

## Metrics

The runner reports:

- Extraction cases passed, including exact record ledgers and evidence flags.
- `recall_at_5`: the fraction of queries whose expected record appears in the
  first five FTS results.
- `mean_reciprocal_rank`: the mean inverse rank of each expected record.
- Multi-domain top-1 retrieval, exact citation formatting, and cross-source
  synthesis coverage.
- Refusal accuracy for questions whose concepts do not occur in the indexed
  course.
- Supported-versus-fabricated claim verdicts, including strict numerical
  checking.
- Correct visual-review signaling for a diagram whose native text is
  insufficient.
- Focused, adaptive, standard, and full retrieval recall, rank quality, median,
  p95, and aggregate estimated context tokens.
- Adaptive reductions versus standard and full retrieval.

The separate realistic-semester scale tier generates 180 sources and 560
records, including timed transcript cues. It gates initial indexing at 15
seconds, no-change synchronization at 3 seconds, median retrieval at 100 ms,
and p95 retrieval at 500 ms. These limits intentionally leave substantial room
for supported CI operating systems while still catching large regressions.

The adaptive workflow uses three candidates, a 600-token search budget, and a
900-character selected read. It passes only with complete retrieval,
every target ranked first, unchanged rank quality, at least 25% savings versus
the balanced standard workflow, at least 70% savings versus full search,
median context at or below 2,500 estimated tokens, and p95 at or below 4,000.

The focused workflow merges the same three-candidate decision with the selected
900-character read. It must keep complete recall, top rank, and target
evidence while using at least 10% less context than adaptive retrieval and no
more than 1,900 median estimated tokens.

The multi-domain mini-courses are realistic original fixtures, not evidence of
performance on private or institution-authored lectures. The benchmark also
intentionally excludes OCR quality and pixel-accurate PowerPoint rendering.
The default accuracy tier has no wall-clock gate; `benchmarks.scale` owns the
explicit performance thresholds. New versions should expand those claims only
with redistributable evidence and explicit expected results.
