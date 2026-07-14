#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path

from _common import emit, fail
from classcorpus.database import Database
from classcorpus.indexer import sync_course


def main() -> int:
    parser = argparse.ArgumentParser(description="Index a local course folder.")
    parser.add_argument("course")
    parser.add_argument("source_root", type=Path)
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        database = Database()
        database.initialize()
        report = sync_course(database, args.course, args.source_root)
        emit({"ok": True, **asdict(report)}, json_mode=args.json_mode)
        return 0 if report.failed == 0 else 1
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
