#!/usr/bin/env python3
from __future__ import annotations

from _common import argument_parser, emit, fail
from _embeddings import create_encoder
from classcorpus.database import Database
from classcorpus.embeddings import build_embeddings


def main() -> int:
    parser = argument_parser(description="Build optional local embeddings.")
    parser.add_argument("course")
    parser.add_argument(
        "--backend",
        choices=("sentence-transformers", "fastembed", "hashing"),
        default="sentence-transformers",
    )
    parser.add_argument("--model")
    parser.add_argument("--dimensions", type=int, default=384)
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        database = Database()
        database.initialize()
        encoder = create_encoder(
            args.backend,
            model_name=args.model,
            dimensions=args.dimensions,
        )
        count = build_embeddings(
            database,
            args.course,
            encoder,
        )
        emit(
            {
                "ok": True,
                "embedded": count,
                "backend": args.backend,
                "model": encoder.model_name,
            },
            json_mode=args.json_mode,
        )
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
