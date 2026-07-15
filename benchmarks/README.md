# ClassCorpus Benchmarks

ClassCorpus publishes a deterministic, redistributable benchmark for native
lecture extraction and baseline SQLite FTS5 retrieval. The corpus is generated
from code, contains no private course material, and requires no network access
or model download.

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

Version 2 contains:

- A two-page PDF with very long native text and a mixed text/image page.
- A six-slide PPTX covering nested groups, notes, tables, repeated embedded
  images, OOXML fallback text, a chart, an Office Math equation, DrawingML
  SmartArt, and an OLE object.
- Markdown and plain-text distractors that repeat partial query terms. These
  prove that full multi-term coverage outranks raw repetition.

[`manifest.json`](manifest.json) is the benchmark contract. It records source
and record counts, exact extraction statuses/reasons, and expected retrieval
targets. Add or version expectations whenever parser behavior changes.

## Metrics

The runner reports:

- Extraction cases passed, including exact record ledgers and evidence flags.
- `recall_at_5`: the fraction of queries whose expected record appears in the
  first five FTS results.
- `mean_reciprocal_rank`: the mean inverse rank of each expected record.

The benchmark intentionally excludes wall-clock thresholds. Runtime varies by
platform and is not a reliable correctness signal. It also does not claim to
measure OCR quality, pixel-accurate PowerPoint rendering, or performance on
real lecture distributions. New benchmark versions should expand those claims
only with redistributable evidence and explicit expected results.
