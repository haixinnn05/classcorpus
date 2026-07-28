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
5. **Confirm the publisher was saved.** Reload the PyPI publishing settings and
   check that the entry appears under *Pending publishers* with all five values
   exactly as entered. A form that failed to submit looks identical to one that
   was never filled in, and the release will fail with `invalid-publisher`.
6. Only then add the repository variable `PYPI_PUBLISH_ENABLED` with the value
   `true`.

Keep the variable absent or set to `false` until setup is complete. The PyPI
job is skipped by default, while GitHub Release assets continue to publish.

The environment name in the workflow, the environment in GitHub, and the
environment recorded on PyPI must all match exactly. On failure the action prints
the claims GitHub actually sent; compare them field by field with the publisher.

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

Use `gh workflow run release.yml` first for a dry run. The `workflow_dispatch`
trigger builds and smoke-tests every artifact while skipping both publish jobs,
so a broken build is caught before a version is spent.

Never reuse a published version. If a release fails after PyPI accepts its
files, increment the package version before trying again.

If PyPI rejects the token exchange, no files were uploaded and the version is
still free: fix the publisher, then `gh run rerun RUN_ID --failed` to retry the
same version using the artifacts already built.
