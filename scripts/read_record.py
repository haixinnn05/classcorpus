#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict

from _common import argument_parser, emit, fail
from classcorpus.database import Database
from classcorpus.record_text import RECORD_TEXT_FIELDS, read_record_text


def main() -> int:
    parser = argument_parser(
        description="Read one bounded chunk from an exact lecture record."
    )
    parser.add_argument("--course", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--ordinal", required=True, type=int)
    parser.add_argument(
        "--field",
        choices=RECORD_TEXT_FIELDS,
        default="searchable",
    )
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=2_000)
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        database = Database()
        database.initialize()
        chunk = read_record_text(
            database,
            course=args.course,
            source_file=args.source,
            ordinal=args.ordinal,
            field=args.field,
            offset=args.offset,
            limit=args.limit,
        )
        emit(
            {"ok": True, **asdict(chunk)},
            json_mode=args.json_mode,
        )
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
