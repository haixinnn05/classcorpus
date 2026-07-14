from classcorpus.paths import data_root, database_path, render_directory


def test_data_root_honors_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path))
    assert data_root() == tmp_path
    assert database_path() == tmp_path / "classcorpus.sqlite3"


def test_render_directory_is_stable(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path))
    assert render_directory("Algorithms", "abc123") == (
        tmp_path / "renders" / "algorithms" / "abc123"
    )


def test_render_directory_falls_back_to_course_slug(monkeypatch, tmp_path):
    monkeypatch.setenv("CLASSCORPUS_DATA_DIR", str(tmp_path))
    assert render_directory("  !!!  ", "abc123") == (
        tmp_path / "renders" / "course" / "abc123"
    )
