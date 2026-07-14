#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from _common import argument_parser, emit, fail
from classcorpus.database import Database
from classcorpus.indexer import sync_course


def main() -> int:
    parser = argument_parser(description="Index a local course folder.")
    parser.add_argument("course")
    parser.add_argument("source_root", type=Path)
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        database = Database()
        database.initialize()
        report = sync_course(database, args.course, args.source_root)
        summary = asdict(report)
        if report.failed:
            emit(
                {
                    "ok": False,
                    "error": {
                        "type": "PartialSyncError",
                        "message": (
                            f"{report.failed} source file(s) failed; successfully "
                            "indexed files were preserved"
                        ),
                    },
                    **summary,
                },
                json_mode=args.json_mode,
            )
            return 1
        emit({"ok": True, **summary}, json_mode=args.json_mode)
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
