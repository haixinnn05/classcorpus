#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict

from _common import argument_parser, emit, fail
from classcorpus.database import Database
from classcorpus.vision import get_vision_queue


def main() -> int:
    parser = argument_parser(description="List slides awaiting visual analysis.")
    parser.add_argument("course")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        database = Database()
        database.initialize()
        items = get_vision_queue(database, args.course, limit=args.limit)
        emit(
            {"ok": True, "items": [asdict(item) for item in items]},
            json_mode=args.json_mode,
        )
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
