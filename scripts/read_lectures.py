#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict

from _common import argument_parser, emit, fail
from classcorpus.database import Database
from classcorpus.records import read_records


def main() -> int:
    parser = argument_parser(
        description="Read every indexed record in a lecture scope."
    )
    parser.add_argument("--course", required=True)
    parser.add_argument("--source")
    parser.add_argument("--cursor")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        database = Database()
        database.initialize()
        page = read_records(
            database,
            course=args.course,
            source_file=args.source,
            cursor=args.cursor,
            limit=args.limit,
        )
        emit(
            {
                "ok": True,
                **asdict(page),
            },
            json_mode=args.json_mode,
        )
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
