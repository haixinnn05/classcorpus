from pathlib import Path

from benchmarks.scale import run_scale_benchmark


def test_realistic_semester_scale_gate_passes(tmp_path: Path):
    result = run_scale_benchmark(tmp_path)

    assert result["ok"] is True
    assert result["tier"] == "realistic-semester"
    assert result["sources"] == 180
    assert result["records"] == 560
    assert result["queries"] == 40
    assert result["failures"] == []
    assert all(result["checks"].values())
