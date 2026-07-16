# ClassCorpus Benchmarks

ClassCorpus publishes a deterministic, redistributable benchmark for native
lecture extraction, baseline SQLite FTS5 retrieval, and end-to-end agent
context efficiency. The corpus is generated from code, contains no private
course material, and requires no network access or model download.

## Run

From the repository environment:

```bash
.venv/bin/python -m benchmarks.run
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

Version 3 contains:

- A two-page PDF with very long native text and a mixed text/image page.
- A six-slide PPTX covering nested groups, notes, tables, repeated embedded
  images, OOXML fallback text, a chart, an Office Math equation, DrawingML
  SmartArt, and an OLE object.
- Markdown and plain-text distractors that repeat partial query terms. These
  prove that full multi-term coverage outranks raw repetition.
- Thirty generated Markdown records with shared course vocabulary and unique
  target markers for focused token-efficiency queries.

[`manifest.json`](manifest.json) is the benchmark contract. It records source
and record counts, exact extraction statuses/reasons, and expected retrieval
targets. Add or version expectations whenever parser behavior changes.

## Metrics

The runner reports:

- Extraction cases passed, including exact record ledgers and evidence flags.
- `recall_at_5`: the fraction of queries whose expected record appears in the
  first five FTS results.
- `mean_reciprocal_rank`: the mean inverse rank of each expected record.
- Focused, adaptive, standard, and full retrieval recall, rank quality, median,
  p95, and aggregate estimated context tokens.
- Adaptive reductions versus standard and full retrieval.

The adaptive workflow uses three candidates, a 600-token search budget, and a
1,200-character selected read. It passes only with complete retrieval,
every target ranked first, unchanged rank quality, at least 25% savings versus
the balanced standard workflow, at least 70% savings versus full search,
median context at or below 2,500 estimated tokens, and p95 at or below 4,000.

The focused workflow merges the same three-candidate decision with the selected
1,200-character read. It must keep complete recall, top rank, and target
evidence while using at least 10% less context than adaptive retrieval and no
more than 1,900 median estimated tokens.

The benchmark intentionally excludes wall-clock thresholds. Runtime varies by
platform and is not a reliable correctness signal. It also does not claim to
measure OCR quality, pixel-accurate PowerPoint rendering, or performance on
real lecture distributions. New benchmark versions should expand those claims
only with redistributable evidence and explicit expected results.
