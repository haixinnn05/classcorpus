from pathlib import Path

from benchmarks.generate import generate_corpus
from benchmarks.run import load_manifest, run_benchmark


def test_generated_corpus_matches_published_source_manifest(tmp_path: Path):
    manifest = load_manifest()
    generated = generate_corpus(tmp_path)

    assert set(generated) == set(manifest["sources"])
    assert all(path.is_file() and path.stat().st_size > 0 for path in generated.values())


def test_extraction_and_retrieval_benchmark_passes(tmp_path: Path):
    result = run_benchmark(tmp_path)

    assert result["ok"] is True
    assert result["extraction"]["successful_cases"] == result["extraction"]["cases"]
    assert result["retrieval"]["recall_at_5"] == 1.0
    assert result["retrieval"]["mean_reciprocal_rank"] == 1.0
    assert result["extraction"]["failures"] == []
    assert result["retrieval"]["failures"] == []
