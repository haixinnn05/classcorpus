#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict

from _common import argument_parser, emit, fail
from classcorpus.database import Database
from classcorpus.ocr import TesseractAdapter, process_ocr_queue


def main() -> int:
    parser = argument_parser(
        description="Run optional local OCR on indexed visual evidence."
    )
    parser.add_argument("course")
    parser.add_argument("--backend", choices=("tesseract",), default="tesseract")
    parser.add_argument("--language", default="eng")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        database = Database()
        database.initialize()
        adapter = TesseractAdapter(language=args.language)
        report = process_ocr_queue(
            database,
            args.course,
            adapter,
            limit=args.limit,
            retry_failed=args.retry_failed,
        )
        payload = {
            "ok": report.failed == 0,
            "backend": adapter.backend,
            **asdict(report),
        }
        if report.failed:
            payload["error"] = {
                "type": "PartialOCRFailure",
                "message": f"{report.failed} record(s) failed local OCR",
            }
        emit(payload, json_mode=args.json_mode)
        return 0 if report.failed == 0 else 1
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
