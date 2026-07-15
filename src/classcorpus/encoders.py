from __future__ import annotations

import hashlib
import re
from typing import Literal, Sequence

EmbeddingBackend = Literal[
    "sentence-transformers",
    "fastembed",
    "hashing",
]

DEFAULT_SENTENCE_TRANSFORMER = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_FASTEMBED_MODEL = "BAAI/bge-small-en-v1.5"


class SentenceTransformerEncoder:
    def __init__(self, model_name: str = DEFAULT_SENTENCE_TRANSFORMER):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                'install optional dependencies with: pip install -e ".[embeddings]"'
            ) from error
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> Sequence[Sequence[float]]:
        return self._model.encode(texts)


class FastEmbedEncoder:
    def __init__(self, model_name: str = DEFAULT_FASTEMBED_MODEL):
        try:
            from fastembed import TextEmbedding
        except ImportError as error:
            raise RuntimeError(
                'install the FastEmbed backend with: pip install -e ".[fastembed]"'
            ) from error
        self.model_name = f"fastembed:{model_name}"
        self._model = TextEmbedding(model_name=model_name)

    def encode(self, texts: list[str]) -> Sequence[Sequence[float]]:
        return list(self._model.embed(texts))


class HashingEncoder:
    def __init__(self, dimensions: int = 384):
        if dimensions < 32:
            raise ValueError("hashing dimensions must be at least 32")
        self.dimensions = dimensions
        self.model_name = f"hashing-v1:{dimensions}"

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self._encode_one(text) for text in texts]

    def _encode_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"\w+", text.casefold(), flags=re.UNICODE)
        for token in tokens:
            self._add_feature(vector, f"word:{token}")
            padded = f"^{token}$"
            for width in (3, 4, 5):
                for start in range(max(0, len(padded) - width + 1)):
                    self._add_feature(
                        vector,
                        f"char:{padded[start : start + width]}",
                    )
        if not tokens:
            self._add_feature(vector, "empty")
        return vector

    def _add_feature(self, vector: list[float], feature: str) -> None:
        digest = hashlib.blake2b(
            feature.encode("utf-8"),
            digest_size=8,
            person=b"ClassCor",
        ).digest()
        index = int.from_bytes(digest[:4], "little") % self.dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign


def create_encoder(
    backend: EmbeddingBackend,
    *,
    model_name: str | None = None,
    dimensions: int = 384,
):
    if backend == "sentence-transformers":
        return SentenceTransformerEncoder(
            model_name or DEFAULT_SENTENCE_TRANSFORMER
        )
    if backend == "fastembed":
        return FastEmbedEncoder(model_name or DEFAULT_FASTEMBED_MODEL)
    if backend == "hashing":
        if model_name is not None:
            raise ValueError("--model is not supported by the hashing backend")
        return HashingEncoder(dimensions)
    raise ValueError(f"unsupported embedding backend: {backend}")


__all__ = [
    "DEFAULT_FASTEMBED_MODEL",
    "DEFAULT_SENTENCE_TRANSFORMER",
    "EmbeddingBackend",
    "FastEmbedEncoder",
    "HashingEncoder",
    "SentenceTransformerEncoder",
    "create_encoder",
]

