"""Install the bundled Agent Skill into an agent's skills directory.

A published wheel carries `SKILL.md`, `references/`, and `scripts/` under
`classcorpus/_skill/`, copied there while building. A source or editable checkout
has no bundle, so the repository root is used instead. Either way the same files
are copied, so a package install and a clone produce the same skill directory.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Any, Iterable

SKILL_ASSETS = ("SKILL.md", "references", "scripts")
BUNDLE_DIRECTORY = "_skill"
SKILL_DIRECTORY_NAME = "classcorpus"

AGENT_SKILL_ROOTS: dict[str, tuple[str, str]] = {
    # agent -> (environment variable holding the agent home, default home)
    "claude": ("CLAUDE_HOME", "~/.claude"),
    "codex": ("CODEX_HOME", "~/.codex"),
}


def asset_root() -> Path:
    """Return the directory holding the skill assets.

    Prefers the bundle inside an installed package, then the repository root of a
    source checkout.
    """
    bundled = Path(__file__).resolve().parent / BUNDLE_DIRECTORY
    if _has_all_assets(bundled):
        return bundled
    for candidate in Path(__file__).resolve().parents:
        if _has_all_assets(candidate):
            return candidate
    raise FileNotFoundError(
        "cannot locate the Agent Skill assets. Reinstall ClassCorpus, or run "
        "this command from a repository checkout."
    )


def agent_skill_directory(agent: str) -> Path:
    """Return the skills directory for one supported agent."""
    try:
        variable, default_home = AGENT_SKILL_ROOTS[agent]
    except KeyError:
        supported = ", ".join(sorted(AGENT_SKILL_ROOTS))
        raise ValueError(f"unknown agent: {agent}. Choose one of: {supported}")
    home = os.environ.get(variable) or default_home
    return Path(home).expanduser() / "skills"


def detect_agents() -> list[str]:
    """Return supported agents whose home directory already exists."""
    return [
        agent
        for agent in sorted(AGENT_SKILL_ROOTS)
        if agent_skill_directory(agent).parent.is_dir()
    ]


def install_skill(
    *,
    agent: str | None = None,
    target: Path | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Copy the skill assets into one or more skills directories.

    With no arguments, installs for every detected agent, because a user with
    both Claude Code and Codex wants the skill in both. `agent` narrows that to
    one, and `target` installs into an exact directory instead.

    Refuses to replace an existing directory that ClassCorpus did not install,
    unless `overwrite` is explicit.
    """
    if agent is not None and target is not None:
        raise ValueError("choose either an agent or an explicit target, not both")

    source = asset_root()
    if target is not None:
        destinations = [(None, target.expanduser().resolve())]
    else:
        agents = [agent] if agent is not None else _detected_agents_or_fail()
        destinations = [
            (name, agent_skill_directory(name).resolve() / SKILL_DIRECTORY_NAME)
            for name in agents
        ]

    for _, destination in destinations:
        if (
            destination.exists()
            and not _is_classcorpus_skill(destination)
            and not overwrite
        ):
            raise ValueError(
                f"refusing to replace an unrelated directory: {destination}. "
                "Pass --overwrite to replace it."
            )

    installations = []
    for name, destination in destinations:
        replaced = destination.exists()
        copied = _copy_assets(source, destination)
        installations.append(
            {
                "agent": name,
                "target": str(destination),
                "replaced_existing": replaced,
                "installed_files": len(copied),
            }
        )

    return {
        "ok": True,
        "source": str(source),
        "installations": installations,
        "assets": list(SKILL_ASSETS),
        "next_steps": [
            "Restart or reload the agent so it discovers SKILL.md.",
            "Verify the environment with: classcorpus doctor",
        ],
    }


def _detected_agents_or_fail() -> list[str]:
    detected = detect_agents()
    if not detected:
        supported = ", ".join(sorted(AGENT_SKILL_ROOTS))
        raise ValueError(
            "no supported agent home directory was found. Pass --agent "
            f"({supported}) or --target DIRECTORY."
        )
    return detected


def _copy_assets(source: Path, destination: Path) -> list[Path]:
    """Replace the destination's skill assets atomically per asset."""
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for name in SKILL_ASSETS:
        origin = source / name
        target = destination / name
        if origin.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(
                origin,
                target,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
            )
            copied.extend(path for path in target.rglob("*") if path.is_file())
        else:
            shutil.copy2(origin, target)
            copied.append(target)
    return copied


def _is_classcorpus_skill(directory: Path) -> bool:
    """Report whether a directory already looks like an installed ClassCorpus skill."""
    skill_file = directory / "SKILL.md"
    if not skill_file.is_file():
        return False
    head = skill_file.read_text(encoding="utf-8", errors="replace")[:400]
    return "name: classcorpus" in head


def _has_all_assets(directory: Path) -> bool:
    return all((directory / name).exists() for name in SKILL_ASSETS)


def bundled_asset_files(root: Path | None = None) -> Iterable[Path]:
    """Yield every file that makes up the skill, for verification."""
    base = root or asset_root()
    for name in SKILL_ASSETS:
        path = base / name
        if path.is_dir():
            yield from (item for item in sorted(path.rglob("*")) if item.is_file())
        else:
            yield path


__all__ = [
    "AGENT_SKILL_ROOTS",
    "SKILL_ASSETS",
    "SKILL_DIRECTORY_NAME",
    "agent_skill_directory",
    "asset_root",
    "bundled_asset_files",
    "detect_agents",
    "install_skill",
]
