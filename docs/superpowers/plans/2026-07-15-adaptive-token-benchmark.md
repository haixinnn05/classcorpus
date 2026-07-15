# Adaptive Token Benchmark Implementation Plan

**Design:** `docs/superpowers/specs/2026-07-15-adaptive-token-benchmark-design.md`

## 1. Generated Efficiency Corpus

- Generate 30 deterministic Markdown records with shared vocabulary and unique
  target markers.
- Index the corpus under a benchmark-only course.
- Keep fixture generation independent of user and lecture data.

## 2. End-To-End Measurement

- Run adaptive, standard, and full retrieval for every focused query.
- Serialize search and bounded-read responses through production helpers.
- Include the installed skill instructions in total context estimates.
- Report recall, rank quality, median, p95, aggregate tokens, reductions, and
  failures.

## 3. Benchmark Integration

- Add `token_efficiency` to `benchmarks/run.py`.
- Gate the overall benchmark result on the published quality and efficiency
  thresholds.
- Add concise human-readable CLI output for the new measurements.

## 4. Agent Routing

- Run the benchmark before changing skill instructions.
- If adaptive saves at least 25% with unchanged quality, document narrow-query
  routing using existing explicit flags.
- Otherwise retain the balanced defaults and publish only the measurement.

## 5. Validation

- Add focused benchmark tests.
- Run the benchmark and inspect its case-level report.
- Run full pytest, Ruff, skill validation, and the reproducible benchmark.
- Review the final diff and create one local commit without pushing.
