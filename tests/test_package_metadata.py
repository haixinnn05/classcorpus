import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_project_metadata() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as project_file:
        return tomllib.load(project_file)["project"]


def test_package_metadata_is_ready_for_public_distribution():
    project = load_project_metadata()

    assert project["name"] == "classcorpus"
    assert project["readme"] == "README.md"
    assert project["license"] == "Apache-2.0"
    assert project["authors"] == [{"name": "Jackson Wu"}]
    assert project["requires-python"] == ">=3.11"


def test_package_metadata_links_to_public_project_resources():
    urls = load_project_metadata()["urls"]

    assert urls["Homepage"] == "https://github.com/haixinnn05/classcorpus"
    assert urls["Repository"] == "https://github.com/haixinnn05/classcorpus"
    assert urls["Issues"] == "https://github.com/haixinnn05/classcorpus/issues"
    assert urls["Changelog"].endswith("/blob/main/CHANGELOG.md")


def test_package_readme_uses_pypi_safe_links():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    destinations = re.findall(r"\[[^\]]+\]\(([^)]+)\)", readme)
    relative_links = [
        destination
        for destination in destinations
        if not destination.startswith(("https://", "http://", "#"))
    ]

    assert not relative_links


def test_package_ships_pep_561_type_information():
    with (ROOT / "pyproject.toml").open("rb") as project_file:
        config = tomllib.load(project_file)

    assert (ROOT / "src" / "classcorpus" / "py.typed").is_file()
    assert config["tool"]["setuptools"]["package-data"]["classcorpus"] == ["py.typed"]
    assert "mypy>=1.15,<2" in config["project"]["optional-dependencies"]["dev"]
