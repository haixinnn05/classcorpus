#!/usr/bin/env python3
from __future__ import annotations

from _common import argument_parser, emit, fail
from classcorpus.database import Database
from classcorpus.record_text import RECORD_TEXT_FIELDS
from classcorpus.retrieval import (
    DEFAULT_FOCUSED_LIMIT,
    DEFAULT_FOCUSED_READ_CHARS,
    retrieve_focused,
)


def main() -> int:
    parser = argument_parser(
        description="Retrieve one focused, deduplicated evidence bundle."
    )
    parser.add_argument("query")
    parser.add_argument("--course", required=True)
    parser.add_argument("--source")
    parser.add_argument("--ordinal", type=int)
    parser.add_argument("--limit", type=int, default=DEFAULT_FOCUSED_LIMIT)
    parser.add_argument(
        "--field",
        choices=RECORD_TEXT_FIELDS,
        default="searchable",
    )
    parser.add_argument(
        "--read-limit",
        type=int,
        default=DEFAULT_FOCUSED_READ_CHARS,
    )
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        database = Database()
        database.initialize()
        payload = retrieve_focused(
            database,
            args.query,
            course=args.course,
            source_file=args.source,
            ordinal=args.ordinal,
            limit=args.limit,
            field=args.field,
            read_limit=args.read_limit,
        )
        emit(payload, json_mode=args.json_mode)
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
