# Releasing ClassCorpus

ClassCorpus publishes versioned Python distributions and an Agent Skill archive
from GitHub Releases. PyPI publishing uses OpenID Connect trusted publishing, so
the repository does not store a PyPI API token.

## One-Time PyPI Setup

Do not enable the repository variable until the trusted publisher exists.

1. Sign in to [PyPI](https://pypi.org/) and open the publishing settings.
2. If `classcorpus` has not been published, create a pending publisher for the
   project. Otherwise, add a publisher from the project's publishing settings.
3. Enter these GitHub values:

   | Field | Value |
   | --- | --- |
   | PyPI project name | `classcorpus` |
   | Owner | `haixinnn05` |
   | Repository | `classcorpus` |
   | Workflow | `release.yml` |
   | Environment | `pypi` |

4. In the GitHub repository, create an environment named `pypi`.
5. Add the repository variable `PYPI_PUBLISH_ENABLED` with the value `true`.

Keep the variable absent or set to `false` until setup is complete. The PyPI
job is skipped by default, while GitHub Release assets continue to publish.

## Publish A Release

1. Update the version in `pyproject.toml`.
2. Move the `Unreleased` changelog entries into a dated version section.
3. Run the release checks:

   ```bash
   .venv/bin/ruff check benchmarks src scripts tests
   .venv/bin/python -m pytest -q
   .venv/bin/python -m benchmarks.run
   ```

4. Commit and push the release changes.
5. Create and publish a GitHub Release whose tag exactly matches the package
   version, such as `v0.5.1`.
6. Confirm that the `Release Assets` workflow attached the wheel, source
   archive, and Agent Skill zip. Once enabled, also confirm the PyPI job and
   the project page on PyPI.

Never reuse a published version. If a release fails after PyPI accepts its
files, increment the package version before trying again.
