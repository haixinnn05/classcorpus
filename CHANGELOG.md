# Changelog

## Unreleased

### Added

- Check whether cited claims are supported by the records they cite with
  `classcorpus check-claims SOURCE`. `verify-artifact` detects a changed source;
  this detects a claim the cited record does not make, which is the case a
  well-formed citation on a fabricated value would otherwise pass. Complexity
  expressions, powers, and numbers are compared strictly and without whitespace,
  so `O(V * E)` matches `O(V*E)` while an invented `O(V log V)` is reported. The
  check is lexical and local, so it is a support signal rather than proof of
  entailment.

### Changed

- Restructure `SKILL.md` around routing and obligations, moving payload mechanics
  into the references that are loaded on demand. Every token in `SKILL.md` is
  charged against every workflow, and headroom under the context benchmark had
  fallen to 8 tokens. The instruction set now costs 1,163 tokens rather than
  1,288, which lowers the focused median from 1,892 to 1,767 against an unchanged
  1,900 ceiling, restoring 133 tokens of headroom. Retrieval quality is unchanged
  at full recall and reciprocal rank, and every documented obligation is retained.

## 0.6.1 - 2026-07-28

### Fixed

- Group multi-token exponents in typeset mathematics. `n^log_b(a)` rendered as
  `n` with a superscript `log` and a subscript `b` followed by `(a)`, rather than
  `n` raised to `log_b(a)`. That is the master-theorem expression, so it appeared
  in ordinary algorithms study guides. `e^-x` and `n^12` are also corrected, while
  `x^2_i` keeps its superscript-then-subscript meaning.
- Typeset capital Greek names that were missing while others were present, so
  `Theta(n log n)` no longer renders literally. Adds Theta, Pi, Psi, Xi, and
  Upsilon.
- Name the guide and course on the PDF study-guide cover. The renderer omitted
  the document's level-one heading from the body but never passed it to the
  cover, so the title was discarded and every guide read `COURSE` / `Study Guide`
  in its cover, running header, and footer. The title now defaults to that
  heading and the course label to the course named by the document's citations.

## 0.6.0 - 2026-07-28

### Added

- Install the complete Agent Skill from a package install with
  `classcorpus install-skill`. Published distributions now carry `SKILL.md`,
  `references/`, and `scripts/`, so `pipx install classcorpus` followed by one
  command produces a working skill directory for Claude Code or Codex. Previously
  only a clone could serve as a skill, because nine of the seventeen agent-facing
  scripts have no CLI equivalent. With no arguments it installs for every detected
  agent. Directory assets are replaced rather than merged, and replacing an
  unrelated directory requires `--overwrite`.
- Verify in release CI that the built wheel installs a complete, runnable skill,
  and that `classcorpus demo` works from that wheel.
- Add a security policy, code of conduct, pull-request template, and Dependabot
  configuration, with tests that assert they exist and that every GitHub
  configuration file parses.

### Changed

- Describe both supported interpreters in `SKILL.md`: a cloned skill's `.venv`,
  and any environment where ClassCorpus is installed as a package.
- Replace the roadmap with work that is wanted but not yet done, so contributors
  can see where to help.
- Document the release runbook's ordering requirement: confirm the trusted
  publisher was saved before enabling publishing, and use the dry run first.

### Removed

- Stop tracking 7.2 MB of local scratch and generated study artifacts, which
  nothing referenced. Tracked content drops from 8.6 MB to 1.4 MB, and the Agent
  Skill archive from 6.8 MB to 644 KB. Regenerate equivalents with
  `classcorpus demo`, the scripts in `scripts/`, or the benchmark runner.

## 0.5.1 - 2026-07-28

### Added

- Evaluate ClassCorpus without any course files using `classcorpus demo`, which
  generates a small synthetic course from code, indexes it, and runs one cited
  search. It needs no network access or model download, writes outside lecture
  folders, and refuses to overwrite a directory it did not generate.
- Detect a generated `classcorpus` script whose recorded interpreter no longer
  exists, which happens when an environment is moved or renamed. `doctor` now
  reports the repair, and `python -m classcorpus` is documented as the
  invocation that keeps working.
- Build and smoke-test versioned Python distributions and a complete Agent
  Skill zip, then attach them automatically to future GitHub Releases.
- Prepare guarded PyPI trusted publishing with public package metadata and
  release setup documentation.

### Changed

- Restructure the README around the value proposition, a one-command trial, and
  installation, and move the detailed retrieval, coverage, verification, and
  provenance walkthrough into `docs/retrieval-guide.md`.
- Document explicit update steps for both the published package and the cloned
  Agent Skill.

## 0.5.0 - 2026-07-24

### Added

- Inspect exact citation evidence, source freshness, extraction warnings, and
  local visual previews with `classcorpus inspect`.
- Manage remembered course folders with `classcorpus add`, `list`, `sync`, and
  guarded `remove` commands while preserving the legacy `index` command.
- Index DOCX paragraphs, hyperlinks, tables, and OOXML text as a cited logical
  document record, with explicit review warnings for images and equations.
- Mark every evidence-bearing agent payload as untrusted source content and
  instruct agents to ignore instructions embedded in lecture materials.
- Create privacy-preserving artifact provenance manifests and verify generated
  outputs against their cited indexed sources with `verify-artifact`.
- Write provenance sidecars automatically for PDF study guides and interactive
  HTML flashcard decks.

### Changed

- Automatically typeset standalone equations and inline math in PDF study
  guides, including stacked compact/LaTeX matrices, column vectors,
  determinant bars, fractions, Greek symbols, and common named functions.
- Center focused retrieval on matching evidence and reduce its default selected
  passage from 1,200 to 900 characters.

## 0.4.0 - 2026-07-15

### Added

- Generate self-contained interactive HTML flashcard decks from cited JSON,
  with reveal, navigation, shuffle, topic filters, session-only review
  tracking, responsive layout, and offline operation.
- Retrieve focused evidence in one deduplicated response with task-local cache
  keys, bounded selected text, ranked alternatives, citations, and extraction
  warnings.
- Benchmark focused retrieval end to end, including target-evidence coverage
  and context-efficiency gates.

### Changed

- Make cited JSON plus interactive HTML the default flashcard output; CSV and
  TSV remain optional interchange formats and plain text remains the fallback.
- Route narrow fact lookups through focused retrieval while preserving the
  existing compact search and bounded read commands for broader questions.

### Compatibility

- Existing JSON, CSV, TSV, search, read, outline, and full-search contracts
  remain supported.
- All rendering and retrieval remain local, provider-neutral, and free of
  telemetry or hosted services.
