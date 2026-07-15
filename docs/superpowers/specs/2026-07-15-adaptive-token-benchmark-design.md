# Adaptive Token Benchmark Design

**Date:** 2026-07-15
**Target release:** post-0.3 milestone

## Goal

Measure the complete context an agent receives during focused retrieval and
determine whether a smaller first pass should be recommended. The benchmark
must preserve retrieval quality and remain deterministic, local, and
provider-neutral.

## Compared Workflows

Each focused query is run through three workflows:

- **Adaptive:** three search candidates, a 600-token search budget, and a
  1,200-character read of the top result.
- **Standard:** six search candidates, a 1,200-token search budget, and a
  2,000-character read of the top result.
- **Full:** six complete search records with no compact-response budget.

Total context includes the estimated `SKILL.md` instructions plus every JSON
response in the workflow. Estimates use ClassCorpus's existing deterministic
compact-JSON character count divided by four. They are comparative planning
estimates, not model-provider billing counts.

## Corpus

The benchmark generates 30 Markdown records. Every record shares realistic
course vocabulary and contains one unique topic marker. A focused query
contains the shared vocabulary and that marker, creating multiple plausible
candidates while retaining one known correct record.

The corpus is generated at benchmark time and contains no user, lecture, or
model-provider data.

## Quality And Efficiency Gates

Adaptive routing is eligible for documentation only when all of these pass:

- The target ranks first for every focused query.
- Adaptive rank quality equals standard rank quality.
- Adaptive aggregate context is at least 25% smaller than standard.
- Adaptive aggregate context is at least 70% smaller than full.
- Adaptive median context is at most 2,500 estimated tokens.
- Adaptive p95 context is at most 4,000 estimated tokens.

The benchmark report includes per-workflow recall, mean reciprocal rank,
median, p95, aggregate tokens, reductions, and case-level failures.

## Product Boundary

This milestone adds no hosted service, telemetry, model API, tokenizer
dependency, or automatic query classification. If the gates pass, `SKILL.md`
may recommend the smaller existing CLI flags for narrow fact lookup and retain
the standard defaults as the fallback. If any gate fails, production behavior
and agent routing remain unchanged.

## Validation

The token-efficiency result becomes part of the reproducible benchmark's
overall status. Tests cover deterministic corpus generation, report shape,
quality equivalence, percentile calculations, and all acceptance thresholds.
