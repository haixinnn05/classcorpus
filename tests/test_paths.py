from classcorpus.paths import (
    create_render_generation,
    data_root,
    database_path,
    render_directory,
)


def test_data_root_honors_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path))
    assert data_root() == tmp_path
    assert database_path() == tmp_path / "classcorpus.sqlite3"


def test_render_directory_is_stable(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path))
    assert render_directory("Algorithms", "abc123", "1") == (
        tmp_path / "renders" / "algorithms" / "parser-31" / "abc123"
    )


def test_render_directory_is_isolated_by_parser_version(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path))

    assert render_directory("Algorithms", "abc123", "1") != render_directory(
        "Algorithms",
        "abc123",
        "2",
    )


def test_render_directory_version_encoding_is_injective(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path))

    assert render_directory("Algorithms", "abc123", "1.0") != render_directory(
        "Algorithms",
        "abc123",
        "1_0",
    )


def test_render_directory_isolates_processing_attempts(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path))

    first = create_render_generation("Algorithms", "abc123", "1")
    second = create_render_generation("Algorithms", "abc123", "1")

    assert first != second
    assert first.is_dir()
    assert second.is_dir()


def test_render_directory_falls_back_to_course_slug(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path))
    assert render_directory("  !!!  ", "abc123", "1") == (
        tmp_path / "renders" / "course" / "parser-31" / "abc123"
    )
