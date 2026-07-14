#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict

from _common import emit, fail
from classcorpus.citations import format_citation
from classcorpus.database import Database
from classcorpus.search import search


def main() -> int:
    parser = argparse.ArgumentParser(description="Search indexed course materials.")
    parser.add_argument("query")
    parser.add_argument("--course")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        database = Database()
        database.initialize()
        results = search(
            database,
            args.query,
            course=args.course,
            limit=args.limit,
        )
        payload = [
            {**asdict(result), "citation": format_citation(result)}
            for result in results
        ]
        emit({"ok": True, "results": payload}, json_mode=args.json_mode)
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
