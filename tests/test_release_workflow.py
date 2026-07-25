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

    upload = next(
        step for step in build_steps if step.get("uses") == "actions/upload-artifact@v4"
    )
    assert upload["with"]["path"] == "dist/"
    assert upload["with"]["if-no-files-found"] == "error"


def test_release_workflow_only_publishes_completed_build_artifacts():
    publish = load_workflow()["jobs"]["publish"]
    assert publish["needs"] == "build"

    steps = publish["steps"]
    assert any(step.get("uses") == "actions/download-artifact@v4" for step in steps)
    publish_command = next(step["run"] for step in steps if "run" in step)
    assert 'gh release upload "${RELEASE_TAG}" dist/*' in publish_command
    assert "--clobber" in publish_command
