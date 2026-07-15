from pathlib import Path

import pytest

from classcorpus.database import Database
from classcorpus.indexer import PARSER_VERSION, sync_course
from classcorpus.parser_registry import ParserPlugin, ParserRegistry
from classcorpus.parsers import parse_source, supported_suffixes
from classcorpus.search import search


def test_registry_rejects_suffix_conflicts_and_invalid_plugins():
    registry = ParserRegistry()
    plugin = ParserPlugin("first", (".one",), lambda path, output: [])
    registry.register(plugin)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(
            ParserPlugin("second", (".ONE",), lambda path, output: [])
        )
    with pytest.raises(ValueError, match="start with a dot"):
        registry.register(
            ParserPlugin("invalid", ("txt",), lambda path, output: [])
        )

    assert registry.parser_for(".ONE") == plugin
    assert registry.supported_suffixes() == frozenset({".one"})


def test_markdown_plugin_preserves_raw_text_and_extracts_heading(tmp_path: Path):
    source = tmp_path / "lecture.md"
    raw_text = "# Greedy Algorithms\n\nExchange arguments preserve optimality.\n"
    source.write_text(raw_text, encoding="utf-8")

    record = parse_source(source, tmp_path / "unused")[0]

    assert record.title == "Greedy Algorithms"
    assert record.body_text == "Exchange arguments preserve optimality."
    assert record.raw_text == raw_text
    assert record.native_text_chars == len(raw_text)
    assert record.extraction_status == "text-extracted"
    assert record.render_path is None


def test_blank_text_document_is_explicitly_marked_for_review(tmp_path: Path):
    source = tmp_path / "blank.txt"
    source.write_text("\n  \n", encoding="utf-8")

    record = parse_source(source, tmp_path / "unused")[0]

    assert record.extraction_status == "review-needed"
    assert record.extraction_reasons == ("no-native-text",)


def test_indexer_discovers_text_plugins_and_searches_with_citations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "Algorithms"
    root.mkdir()
    (root / "lecture.md").write_text(
        "# Greedy Algorithms\nExchange argument matroid.",
        encoding="utf-8",
    )
    (root / "notes.txt").write_text(
        "Dynamic Programming\nOptimal substructure.",
        encoding="utf-8",
    )
    (root / "ignored.csv").write_text("not,indexed", encoding="utf-8")
    database = Database(tmp_path / "index.sqlite3")
    database.initialize()

    report = sync_course(database, "Algorithms", root)
    greedy = search(database, "matroid", course="Algorithms")[0]
    dynamic = search(database, "optimal substructure", course="Algorithms")[0]

    assert {".md", ".txt"}.issubset(supported_suffixes())
    assert PARSER_VERSION == "5"
    assert report.indexed == 2
    assert report.records_indexed == 2
    assert greedy.source_file == "lecture.md"
    assert greedy.ordinal == 1
    assert dynamic.source_file == "notes.txt"
    assert dynamic.ordinal == 1
