from pathlib import Path

import pytest

from benchmarks.efficiency import generate_efficiency_corpus, percentile


def test_generated_efficiency_corpus_has_unique_focused_targets(tmp_path: Path):
    cases = generate_efficiency_corpus(tmp_path, case_count=4)

    assert [case["id"] for case in cases] == [
        "focus01",
        "focus02",
        "focus03",
        "focus04",
    ]
    for case in cases:
        content = (tmp_path / case["source"]).read_text(encoding="utf-8")
        assert case["id"] in case["query"]
        assert case["id"] in content
        assert len(content) >= 2_000


def test_percentile_uses_nearest_rank():
    assert percentile([30, 10, 20, 40], 0.50) == 20
    assert percentile([30, 10, 20, 40], 0.95) == 40


@pytest.mark.parametrize("value", [0, -0.1, 1.1])
def test_percentile_rejects_invalid_percentile(value: float):
    with pytest.raises(ValueError):
        percentile([1], value)
