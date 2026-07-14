#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from _common import argument_parser, emit, fail
from classcorpus.database import Database
from classcorpus.vision import store_descriptions


def main() -> int:
    parser = argument_parser(description="Store agent-authored slide descriptions.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        descriptions = payload["descriptions"]
        if not isinstance(descriptions, list):
            raise ValueError("descriptions must be a JSON array")
        database = Database()
        database.initialize()
        stored = store_descriptions(database, descriptions)
        emit({"ok": True, "stored": stored}, json_mode=args.json_mode)
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
