from __future__ import annotations


class SentenceTransformerEncoder:
    def __init__(self, model_name: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                'install optional dependencies with: pip install -e ".[embeddings]"'
            ) from error
        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]):
        return self._model.encode(texts)
