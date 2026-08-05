import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_claude_plugin_and_marketplace_manifests_are_valid_and_local_first():
    plugin = json.loads(
        (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    marketplace = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )

    assert plugin["name"] == "classcorpus"
    assert plugin["skills"] == ["./"]
    assert plugin["license"] == "Apache-2.0"
    assert plugin["repository"] == "https://github.com/haixinnn05/classcorpus"
    with (ROOT / "pyproject.toml").open("rb") as project_file:
        project_version = tomllib.load(project_file)["project"]["version"]
    assert plugin["version"] == project_version
    assert marketplace["name"] == "classcorpus"
    assert marketplace["plugins"] == [
        {
            "name": "classcorpus",
            "source": "./",
            "description": (
                "Index local course materials and build citation-aware study artifacts."
            ),
            "category": "productivity",
            "tags": ["education", "study", "local-first"],
        }
    ]


def test_manifest_is_included_in_source_distributions():
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")

    assert "recursive-include .claude-plugin *.json" in manifest
