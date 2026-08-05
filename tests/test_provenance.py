import json
from pathlib import Path

import fitz
import pytest

from classcorpus.database import Database
from classcorpus.indexer import sync_course
from classcorpus.provenance import (
    manifest_path,
    verify_artifact,
    write_artifact_manifest,
)


@pytest.fixture
def cited_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Database, Path, Path, Path]:
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "state"))
    course_root = tmp_path / "course"
    course_root.mkdir()
    source = course_root / "lecture, one.md"
    source.write_text(
        "# Resonance\n\nMaximum driven amplitude occurs at resonance.",
        encoding="utf-8",
    )
    database = Database(tmp_path / "index.sqlite3")
    database.initialize()
    assert sync_course(database, "Physics, Fall", course_root).indexed == 1

    artifact = tmp_path / "study-guide.html"
    artifact.write_text("<h1>Resonance</h1>", encoding="utf-8")
    citation_source = tmp_path / "study-guide.md"
    citation_source.write_text(
        "Resonance maximizes amplitude. [Physics, Fall, lecture, one.md, Page 1]",
        encoding="utf-8",
    )
    return database, source, artifact, citation_source


def test_manifest_resolves_citations_without_private_source_paths(
    cited_artifact: tuple[Database, Path, Path, Path],
):
    database, source, artifact, citation_source = cited_artifact

    payload = write_artifact_manifest(
        database,
        artifact=artifact,
        citation_source=citation_source,
    )
    stored = manifest_path(artifact).read_text(encoding="utf-8")

    assert payload["citations"][0]["citation"] == (
        "[Physics, Fall, lecture, one.md, Page 1]"
    )
    assert payload["sources"] == [
        {
            "course": "Physics, Fall",
            "source_file": "lecture, one.md",
            "indexed_sha256": payload["citations"][0]["indexed_sha256"],
            "parser_version": payload["citations"][0]["parser_version"],
        }
    ]
    assert payload["unresolved_citations"] == []
    assert str(source.resolve()) not in stored
    assert str(source.parent.resolve()) not in stored
    assert json.loads(stored)["artifact"] == artifact.name
    assert verify_artifact(database, artifact)["status"] == "current"


def test_verify_rejects_a_hash_current_but_unreadable_pdf(
    cited_artifact: tuple[Database, Path, Path, Path],
):
    database, _, artifact, citation_source = cited_artifact
    artifact = artifact.with_suffix(".pdf")
    artifact.write_bytes(b"%PDF-1.4\nnot a readable document\n")
    write_artifact_manifest(
        database,
        artifact=artifact,
        citation_source=citation_source,
    )

    payload = verify_artifact(database, artifact)

    assert payload["ok"] is False
    assert payload["status"] == "artifact-unreadable"
    assert payload["delivery"]["ok"] is False
    assert any(issue["type"] == "artifact_unreadable" for issue in payload["issues"])


def test_verify_rejects_hash_current_but_empty_html(
    cited_artifact: tuple[Database, Path, Path, Path],
):
    database, _, artifact, citation_source = cited_artifact
    artifact.write_text("", encoding="utf-8")
    write_artifact_manifest(
        database,
        artifact=artifact,
        citation_source=citation_source,
    )

    payload = verify_artifact(database, artifact)

    assert payload["ok"] is False
    assert payload["status"] == "artifact-unreadable"
    assert payload["delivery"]["format"] == "html"


def test_verify_renders_every_page_of_a_valid_pdf(
    cited_artifact: tuple[Database, Path, Path, Path],
):
    database, _, artifact, citation_source = cited_artifact
    artifact = artifact.with_suffix(".pdf")
    document = fitz.open()
    for label in ("Page one", "Page two"):
        page = document.new_page()
        page.insert_text((72, 72), label)
    document.save(artifact)
    document.close()
    write_artifact_manifest(
        database,
        artifact=artifact,
        citation_source=citation_source,
    )

    payload = verify_artifact(database, artifact)

    assert payload["ok"] is True
    assert payload["delivery"]["pages"] == 2
    assert payload["delivery"]["rendered_pages"] == 2
    assert payload["delivery"]["text_chars"] > 0


def test_manifest_refuses_to_replace_existing_sidecar(
    cited_artifact: tuple[Database, Path, Path, Path],
):
    database, _, artifact, citation_source = cited_artifact
    write_artifact_manifest(
        database,
        artifact=artifact,
        citation_source=citation_source,
    )

    with pytest.raises(FileExistsError, match="--overwrite"):
        write_artifact_manifest(
            database,
            artifact=artifact,
            citation_source=citation_source,
        )


def test_verify_detects_modified_artifact(
    cited_artifact: tuple[Database, Path, Path, Path],
):
    database, _, artifact, citation_source = cited_artifact
    write_artifact_manifest(
        database,
        artifact=artifact,
        citation_source=citation_source,
    )
    artifact.write_text("<h1>Changed</h1>", encoding="utf-8")

    payload = verify_artifact(database, artifact)

    assert payload["ok"] is False
    assert payload["status"] == "artifact-modified"
    assert payload["issues"][0]["type"] == "artifact_modified"


def test_verify_detects_missing_artifact(
    cited_artifact: tuple[Database, Path, Path, Path],
):
    database, _, artifact, citation_source = cited_artifact
    write_artifact_manifest(
        database,
        artifact=artifact,
        citation_source=citation_source,
    )
    artifact.unlink()

    payload = verify_artifact(database, artifact)

    assert payload["ok"] is False
    assert payload["status"] == "artifact-missing"
    assert payload["issues"][0]["type"] == "artifact_missing"


@pytest.mark.parametrize(
    ("change", "expected_status", "expected_issue"),
    [
        ("modify", "source-changed", "source_changed"),
        ("remove", "source-missing", "source_missing"),
    ],
)
def test_verify_detects_source_drift(
    cited_artifact: tuple[Database, Path, Path, Path],
    change: str,
    expected_status: str,
    expected_issue: str,
):
    database, source, artifact, citation_source = cited_artifact
    write_artifact_manifest(
        database,
        artifact=artifact,
        citation_source=citation_source,
    )
    if change == "modify":
        source.write_text("# Resonance\n\nUpdated after generation.", encoding="utf-8")
    else:
        source.unlink()

    payload = verify_artifact(database, artifact)

    assert payload["ok"] is False
    assert payload["status"] == expected_status
    assert payload["issues"][0]["type"] == expected_issue


def test_unresolved_citation_creates_unverified_manifest(
    cited_artifact: tuple[Database, Path, Path, Path],
):
    database, _, artifact, citation_source = cited_artifact
    citation_source.write_text(
        "Unsupported claim. [Physics, Fall, missing.pdf, Page 9]",
        encoding="utf-8",
    )

    manifest = write_artifact_manifest(
        database,
        artifact=artifact,
        citation_source=citation_source,
    )
    verified = verify_artifact(database, artifact)

    assert manifest["citations"] == []
    assert manifest["unresolved_citations"] == ["[Physics, Fall, missing.pdf, Page 9]"]
    assert verified["ok"] is False
    assert verified["status"] == "unverified"
    assert verified["issues"][0]["type"] == "citation_unresolved"
