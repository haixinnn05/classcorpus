import builtins
from types import SimpleNamespace
import sys

import pytest

from classcorpus.encoders import HashingEncoder, create_encoder


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def test_hashing_encoder_is_deterministic_and_rewards_shared_features():
    encoder = HashingEncoder(dimensions=128)
    first, repeated, related, unrelated = encoder.encode(
        [
            "memoization avoids repeated subproblems",
            "memoization avoids repeated subproblems",
            "memoized subproblem",
            "weighted graph edge",
        ]
    )

    assert first == repeated
    assert len(first) == 128
    assert _dot(first, related) > _dot(first, unrelated)
    assert encoder.model_name == "hashing-v1:128"


def test_hashing_encoder_rejects_tiny_dimensions():
    with pytest.raises(ValueError, match="at least 32"):
        HashingEncoder(dimensions=16)


def test_hashing_factory_rejects_model_name():
    with pytest.raises(ValueError, match="not supported"):
        create_encoder("hashing", model_name="unused")


def test_fastembed_dependency_error_names_install_extra(
    monkeypatch: pytest.MonkeyPatch,
):
    original_import = builtins.__import__

    def fail_fastembed(name, *args, **kwargs):
        if name == "fastembed":
            raise ImportError("not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_fastembed)
    with pytest.raises(RuntimeError, match=r"\.\[fastembed\]"):
        create_encoder("fastembed")


def test_fastembed_adapter_uses_backend_specific_model_identity(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeTextEmbedding:
        def __init__(self, *, model_name: str):
            self.model_name = model_name

        def embed(self, texts: list[str]):
            return ([float(len(text)), 1.0] for text in texts)

    monkeypatch.setitem(
        sys.modules,
        "fastembed",
        SimpleNamespace(TextEmbedding=FakeTextEmbedding),
    )
    encoder = create_encoder("fastembed", model_name="local-test-model")

    assert encoder.model_name == "fastembed:local-test-model"
    assert encoder.encode(["one", "three"]) == [[3.0, 1.0], [5.0, 1.0]]
