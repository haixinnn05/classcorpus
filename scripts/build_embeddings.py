#!/usr/bin/env python3
from __future__ import annotations

import argparse

from _common import emit, fail
from classcorpus.database import Database
from classcorpus.embeddings import build_embeddings


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Build optional local embeddings.")
    parser.add_argument("course")
    parser.add_argument(
        "--model",
        default="sentence-transformers/all-MiniLM-L6-v2",
    )
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        database = Database()
        database.initialize()
        count = build_embeddings(
            database,
            args.course,
            SentenceTransformerEncoder(args.model),
        )
        emit(
            {"ok": True, "embedded": count, "model": args.model},
            json_mode=args.json_mode,
        )
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
