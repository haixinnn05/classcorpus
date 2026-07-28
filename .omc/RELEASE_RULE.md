# Release Rules
<!-- last-analyzed: 2026-07-25T04:31:29Z -->

## Version Sources

- `pyproject.toml`: `[project].version`
- No release automation script is present.

## Release Trigger

- Releases are prepared manually on `main`, then published from an annotated
  `vX.Y.Z` tag.
- The test workflow runs for every branch and tag push, but does not publish.

## Test Gate

- `.venv/bin/ruff check benchmarks src scripts tests`
- `.venv/bin/python -m pytest -q`
- `.venv/bin/python -m benchmarks.run`
- GitHub Actions runs Ruff and pytest across Ubuntu, macOS, and Windows on
  Python 3.11 and 3.12.

## Registry / Distribution

- The project is a setuptools Python package.
- There is no PyPI, GitHub Packages, Docker, or other registry publishing
  workflow. Distribution is currently through the GitHub repository and
  GitHub Releases.

## Release Notes Strategy

- `CHANGELOG.md` contains user-facing notes grouped under Added, Changed, and
  Compatibility where relevant.
- GitHub Release names use `ClassCorpus vX.Y.Z` and copy the matching changelog
  section into the release body.

## CI Workflow Files

- `.github/workflows/test.yml`

## First-Time Setup Gaps

- No automated release or registry publishing workflow exists.
- Build outputs are ignored by `.gitignore`.
- Annotated version tags are in use.
