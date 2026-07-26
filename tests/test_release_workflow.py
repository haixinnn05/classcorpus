from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release.yml"


def load_workflow() -> dict:
    return yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_release_workflow_has_safe_triggers_and_permissions():
    workflow = load_workflow()

    assert workflow["on"]["release"]["types"] == ["published"]
    assert "workflow_dispatch" in workflow["on"]
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["publish"]["permissions"] == {"contents": "write"}
    assert workflow["jobs"]["publish"]["if"] == "github.event_name == 'release'"


def test_release_workflow_builds_and_smoke_tests_all_artifacts():
    build_steps = load_workflow()["jobs"]["build"]["steps"]
    commands = "\n".join(step.get("run", "") for step in build_steps)

    assert "python -m build" in commands
    assert "git archive --format=zip" in commands
    assert "classcorpus doctor --json" in commands
    assert "RELEASE_TAG" in commands

    uploads = {
        step["with"]["name"]: step["with"]
        for step in build_steps
        if step.get("uses") == "actions/upload-artifact@v4"
    }
    assert uploads["release-assets"]["path"] == "dist/"
    assert uploads["release-assets"]["if-no-files-found"] == "error"
    assert "dist/*.whl" in uploads["python-distributions"]["path"]
    assert "dist/*.tar.gz" in uploads["python-distributions"]["path"]
    assert "zip" not in uploads["python-distributions"]["path"]
    assert uploads["python-distributions"]["if-no-files-found"] == "error"


def test_release_workflow_only_publishes_completed_build_artifacts():
    publish = load_workflow()["jobs"]["publish"]
    assert publish["needs"] == "build"

    steps = publish["steps"]
    assert any(step.get("uses") == "actions/download-artifact@v4" for step in steps)
    publish_command = next(step["run"] for step in steps if "run" in step)
    assert 'gh release upload "${RELEASE_TAG}" dist/*' in publish_command
    assert "--clobber" in publish_command


def test_pypi_publish_uses_guarded_trusted_publishing():
    publish = load_workflow()["jobs"]["publish-pypi"]

    assert publish["needs"] == "build"
    assert "github.event_name == 'release'" in publish["if"]
    assert "vars.PYPI_PUBLISH_ENABLED == 'true'" in publish["if"]
    assert publish["environment"] == {"name": "pypi"}
    assert publish["permissions"] == {"id-token": "write"}

    download = next(
        step
        for step in publish["steps"]
        if step.get("uses") == "actions/download-artifact@v4"
    )
    assert download["with"]["name"] == "python-distributions"
    assert download["with"]["path"] == "dist/"
    assert any(
        step.get("uses") == "pypa/gh-action-pypi-publish@release/v1"
        for step in publish["steps"]
    )
