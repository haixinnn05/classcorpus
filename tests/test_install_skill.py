import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from classcorpus.skill import (
    SKILL_ASSETS,
    agent_skill_directory,
    asset_root,
    bundled_asset_files,
    detect_agents,
    install_skill,
)

ROOT = Path(__file__).resolve().parents[1]


def run_cli(
    *arguments: str,
    cwd: Path,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("CLAUDE_HOME", None)
    env.pop("CODEX_HOME", None)
    python_path = env.get("PYTHONPATH")
    source_path = str(ROOT / "src")
    env["PYTHONPATH"] = (
        f"{source_path}{os.pathsep}{python_path}" if python_path else source_path
    )
    env.update(environment or {})
    return subprocess.run(
        [sys.executable, "-m", "classcorpus", *arguments],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_asset_root_resolves_in_a_source_checkout():
    root = asset_root()

    for name in SKILL_ASSETS:
        assert (root / name).exists(), name


def test_every_skill_asset_is_accounted_for():
    files = list(bundled_asset_files())
    names = {path.name for path in files}

    assert "SKILL.md" in names
    assert any(path.suffix == ".md" and path.parent.name == "references" for path in files)
    assert any(path.suffix == ".py" and path.parent.name == "scripts" for path in files)


def test_install_skill_copies_the_complete_skill(tmp_path: Path):
    target = tmp_path / "skills" / "classcorpus"

    payload = install_skill(target=target)

    assert payload["ok"] is True
    installation = payload["installations"][0]
    assert installation["replaced_existing"] is False
    assert installation["agent"] is None
    assert (target / "SKILL.md").is_file()
    assert list((target / "references").glob("*.md"))
    assert list((target / "scripts").glob("*.py"))
    assert installation["installed_files"] == len(
        [path for path in target.rglob("*") if path.is_file()]
    )


def test_installed_skill_declares_itself_to_the_agent(tmp_path: Path):
    target = tmp_path / "classcorpus"
    install_skill(target=target)

    head = (target / "SKILL.md").read_text(encoding="utf-8")[:400]

    assert "name: classcorpus" in head
    assert "description:" in head


def test_installed_scripts_import_and_run(tmp_path: Path):
    target = tmp_path / "classcorpus"
    install_skill(target=target)
    script = target / "scripts" / "read_lectures.py"

    environment = os.environ.copy()
    environment["CLASSCORPUS_DATA_DIR"] = str(tmp_path / "state")
    source_path = str(ROOT / "src")
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{source_path}{os.pathsep}{existing}" if existing else source_path
    )
    result = subprocess.run(
        [sys.executable, str(script), "--course", "Nothing", "--json"],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert "Traceback" not in result.stderr, result.stderr
    assert json.loads(result.stdout)["total_records"] == 0


def test_reinstalling_replaces_a_previous_install(tmp_path: Path):
    target = tmp_path / "classcorpus"
    install_skill(target=target)
    stale = target / "references" / "removed-in-a-later-version.md"
    stale.write_text("stale", encoding="utf-8")

    payload = install_skill(target=target)

    assert payload["installations"][0]["replaced_existing"] is True
    assert not stale.exists(), "a directory asset must be replaced, not merged"
    assert (target / "SKILL.md").is_file()


def test_install_refuses_to_replace_an_unrelated_directory(tmp_path: Path):
    target = tmp_path / "important"
    target.mkdir()
    keep = target / "notes.md"
    keep.write_text("my notes", encoding="utf-8")

    with pytest.raises(ValueError, match="refusing to replace"):
        install_skill(target=target)

    assert keep.read_text(encoding="utf-8") == "my notes"


def test_overwrite_replaces_an_unrelated_directory_explicitly(tmp_path: Path):
    target = tmp_path / "important"
    target.mkdir()
    (target / "notes.md").write_text("my notes", encoding="utf-8")

    payload = install_skill(target=target, overwrite=True)

    assert payload["ok"] is True
    assert (target / "SKILL.md").is_file()


def test_agent_skill_directory_follows_the_agent_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))

    assert agent_skill_directory("claude") == tmp_path / "claude" / "skills"
    assert agent_skill_directory("codex") == tmp_path / "codex" / "skills"


def test_unknown_agent_is_rejected():
    with pytest.raises(ValueError, match="unknown agent"):
        agent_skill_directory("emacs")


def test_detects_only_agents_that_are_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    (tmp_path / "claude").mkdir()
    monkeypatch.setenv("CLAUDE_HOME", str(tmp_path / "claude"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "absent"))

    assert detect_agents() == ["claude"]


def test_agent_and_target_are_mutually_exclusive(tmp_path: Path):
    with pytest.raises(ValueError, match="not both"):
        install_skill(agent="claude", target=tmp_path / "somewhere")


def test_cli_installs_for_a_named_agent(tmp_path: Path):
    home = tmp_path / "claude-home"
    home.mkdir()

    result = run_cli(
        "install-skill",
        "--agent",
        "claude",
        "--json",
        cwd=tmp_path,
        environment={"CLAUDE_HOME": str(home)},
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    installation = payload["installations"][0]
    assert installation["agent"] == "claude"
    assert Path(installation["target"]) == (home / "skills" / "classcorpus").resolve()
    assert (home / "skills" / "classcorpus" / "SKILL.md").is_file()


def test_cli_reports_a_helpful_error_when_no_agent_is_present(tmp_path: Path):
    result = run_cli(
        "install-skill",
        "--json",
        cwd=tmp_path,
        environment={
            "CLAUDE_HOME": str(tmp_path / "absent-claude"),
            "CODEX_HOME": str(tmp_path / "absent-codex"),
        },
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["error"]["type"] == "ValueError"
    assert "--agent" in payload["error"]["message"]


def test_cli_installs_for_every_detected_agent(tmp_path: Path):
    for name in ("claude-home", "codex-home"):
        (tmp_path / name).mkdir()

    result = run_cli(
        "install-skill",
        "--json",
        cwd=tmp_path,
        environment={
            "CLAUDE_HOME": str(tmp_path / "claude-home"),
            "CODEX_HOME": str(tmp_path / "codex-home"),
        },
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert {item["agent"] for item in payload["installations"]} == {"claude", "codex"}
    for name in ("claude-home", "codex-home"):
        assert (tmp_path / name / "skills" / "classcorpus" / "SKILL.md").is_file()


def test_agent_narrows_installation_to_one(tmp_path: Path):
    for name in ("claude-home", "codex-home"):
        (tmp_path / name).mkdir()

    result = run_cli(
        "install-skill",
        "--agent",
        "codex",
        "--json",
        cwd=tmp_path,
        environment={
            "CLAUDE_HOME": str(tmp_path / "claude-home"),
            "CODEX_HOME": str(tmp_path / "codex-home"),
        },
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0, result.stderr
    assert [item["agent"] for item in payload["installations"]] == ["codex"]
    assert not (tmp_path / "claude-home" / "skills").exists()


def test_cli_human_output_names_the_target(tmp_path: Path):
    target = tmp_path / "skills" / "classcorpus"

    result = run_cli(
        "install-skill",
        "--target",
        str(target),
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    assert "Installed the ClassCorpus skill" in result.stdout
    assert str(target.resolve()) in result.stdout


def test_packaging_and_runtime_agree_on_the_skill_assets():
    """The build hook and the installer must bundle the same files."""
    setup_source = (ROOT / "setup.py").read_text(encoding="utf-8")
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")

    for name in SKILL_ASSETS:
        assert f'"{name}"' in setup_source, f"{name} is not bundled by setup.py"
    assert "SKILL.md" in manifest
    assert "recursive-include references *.md" in manifest
    assert "recursive-include scripts *.py" in manifest


def test_bundle_directory_name_matches_the_build_hook():
    from classcorpus.skill import BUNDLE_DIRECTORY

    setup_source = (ROOT / "setup.py").read_text(encoding="utf-8")

    assert f'BUNDLE_DIRECTORY = "{BUNDLE_DIRECTORY}"' in setup_source
