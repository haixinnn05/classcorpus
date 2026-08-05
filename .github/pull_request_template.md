## What changes

Describe the behaviour before and after. Link the issue this implements, if any.

## Why

What problem does this solve? For a parser, storage, or workflow change, please
confirm an issue was opened first so the approach could be agreed.

## Checks

```bash
.venv/bin/ruff check benchmarks src scripts tests
.venv/bin/ruff format --check benchmarks src scripts tests
.venv/bin/mypy
.venv/bin/coverage run -m pytest -q
.venv/bin/coverage combine
.venv/bin/coverage report
.venv/bin/python -m benchmarks.run
.venv/bin/python -m benchmarks.scale
```

- [ ] Lint, tests, and the benchmark pass locally
- [ ] A behavioural test covers the change, and it failed before the fix
- [ ] Test materials are generated or freely redistributable, with no private
      course content, personal data, or credentials

## Boundaries

Confirm the change preserves the project's architecture:

- [ ] Lecture source files are never modified
- [ ] Generated data stays outside lecture folders
- [ ] Baseline search still works without embeddings, OCR, or a network
- [ ] No telemetry, hosted backend, web server, custom chatbot, or required
      provider API
- [ ] Source-derived payloads remain marked as untrusted evidence
- [ ] Exact source paths and canonical page, slide, or timestamp citations are preserved
- [ ] Visual analysis remains opt-in

## Compatibility and privacy

Note any change to a documented JSON contract, CLI flag, or stored schema, and
anything that affects what leaves the user's machine. If a contract changed,
say how existing callers are handled.
