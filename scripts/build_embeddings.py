#!/usr/bin/env python3
from __future__ import annotations

from _common import argument_parser, emit, fail
from _embeddings import SentenceTransformerEncoder
from classcorpus.database import Database
from classcorpus.embeddings import build_embeddings


def main() -> int:
    parser = argument_parser(description="Build optional local embeddings.")
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
