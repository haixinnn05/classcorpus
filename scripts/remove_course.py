#!/usr/bin/env python3
from __future__ import annotations

from _common import argument_parser, emit, fail
from classcorpus.database import Database, remove_course_data


def main() -> int:
    parser = argument_parser(
        description="Delete one course's generated ClassCorpus data."
    )
    parser.add_argument("course")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        if not args.confirm:
            raise ValueError("course removal requires --confirm")
        database = Database()
        database.initialize()
        removed = remove_course_data(
            database,
            args.course,
            confirmed=True,
        )
        emit({"ok": True, "removed": removed}, json_mode=args.json_mode)
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
