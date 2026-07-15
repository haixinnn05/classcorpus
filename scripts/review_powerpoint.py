#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict

from _common import argument_parser, emit, fail
from classcorpus.database import Database
from classcorpus.review import LAYOUT_REASONS, list_powerpoint_reviews


def main() -> int:
    parser = argument_parser(
        description="Inventory layout-dependent PowerPoint records."
    )
    parser.add_argument("course")
    parser.add_argument("--source")
    parser.add_argument("--reason", choices=sorted(LAYOUT_REASONS))
    parser.add_argument("--unreviewed-only", action="store_true")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        database = Database()
        database.initialize()
        report = list_powerpoint_reviews(
            database,
            args.course,
            source_file=args.source,
            reason=args.reason,
            include_reviewed=not args.unreviewed_only,
            limit=args.limit,
            offset=args.offset,
        )
        emit(
            {"ok": True, **asdict(report)},
            json_mode=args.json_mode,
        )
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())

