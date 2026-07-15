from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import shlex
import sys
from typing import Any

from classcorpus.database import Database
from classcorpus.diagnostics import doctor_report
from classcorpus.encoders import create_encoder
from classcorpus.indexer import sync_course
from classcorpus.outline import (
    DEFAULT_OUTLINE_BUDGET_TOKENS,
    outline_course,
)
from classcorpus.payloads import (
    DEFAULT_SEARCH_BUDGET_TOKENS,
    search_response,
)
from classcorpus.record_text import RECORD_TEXT_FIELDS, read_record_text
from classcorpus.search import search, suggest_terms
from classcorpus.status import status_report


class CLIArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        if "--json" in sys.argv[1:]:
            _emit_json(
                {
                    "ok": False,
                    "error": {
                        "type": "ArgumentError",
                        "message": message,
                    },
                }
            )
            raise SystemExit(1)
        super().error(message)


def build_parser() -> CLIArgumentParser:
    parser = CLIArgumentParser(
        prog="classcorpus",
        description="Index and search local course materials with exact citations.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser(
        "index",
        help="Synchronize a local course folder.",
    )
    index_parser.add_argument("course")
    index_parser.add_argument("source_root", type=Path)
    _add_json_argument(index_parser)
    index_parser.set_defaults(handler=_run_index)

    search_parser = subparsers.add_parser(
        "search",
        help="Search indexed course materials.",
    )
    search_parser.add_argument("query")
    search_parser.add_argument("--course")
    search_parser.add_argument("--source")
    search_parser.add_argument("--ordinal", type=int)
    search_parser.add_argument("--limit", type=int)
    search_parser.add_argument("--semantic", action="store_true")
    search_parser.add_argument(
        "--backend",
        choices=("sentence-transformers", "fastembed", "hashing"),
        default="sentence-transformers",
    )
    search_parser.add_argument("--model")
    search_parser.add_argument("--dimensions", type=int, default=384)
    search_parser.add_argument(
        "--compact",
        action="store_true",
        help="Deprecated; compact output is now the default.",
    )
    search_parser.add_argument(
        "--full",
        action="store_true",
        help="Return complete record bodies instead of compact candidates.",
    )
    search_parser.add_argument(
        "--budget-tokens",
        type=int,
        default=DEFAULT_SEARCH_BUDGET_TOKENS,
    )
    _add_json_argument(search_parser)
    search_parser.set_defaults(handler=_run_search)

    read_parser = subparsers.add_parser(
        "read",
        help="Read a bounded text chunk from one exact record.",
    )
    read_parser.add_argument("course")
    read_parser.add_argument("source")
    read_parser.add_argument("ordinal", type=int)
    read_parser.add_argument(
        "--field",
        choices=RECORD_TEXT_FIELDS,
        default="searchable",
    )
    read_parser.add_argument("--offset", type=int, default=0)
    read_parser.add_argument("--limit", type=int, default=2_000)
    _add_json_argument(read_parser)
    read_parser.set_defaults(handler=_run_read)

    outline_parser = subparsers.add_parser(
        "outline",
        help="Plan exhaustive coverage without loading complete record bodies.",
    )
    outline_parser.add_argument("course")
    outline_parser.add_argument("--source")
    outline_parser.add_argument("--cursor")
    outline_parser.add_argument(
        "--budget-tokens",
        type=int,
        default=DEFAULT_OUTLINE_BUDGET_TOKENS,
    )
    _add_json_argument(outline_parser)
    outline_parser.set_defaults(handler=_run_outline)

    status_parser = subparsers.add_parser(
        "status",
        help="Show course health and recommended next actions.",
    )
    status_parser.add_argument("--course")
    _add_json_argument(status_parser)
    status_parser.set_defaults(handler=_run_status)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check core requirements and optional local backends.",
    )
    _add_json_argument(doctor_parser)
    doctor_parser.set_defaults(handler=_run_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        return int(arguments.handler(arguments))
    except Exception as error:
        payload = {
            "ok": False,
            "error": {
                "type": type(error).__name__,
                "message": str(error),
            },
        }
        if arguments.json_mode:
            _emit_json(payload)
        else:
            print(f"Error: {error}", file=sys.stderr)
        return 1


def _run_index(arguments: argparse.Namespace) -> int:
    database = _database()
    report = sync_course(
        database,
        arguments.course,
        arguments.source_root,
    )
    payload: dict[str, Any] = {"ok": report.failed == 0, **asdict(report)}
    if report.failed:
        payload["error"] = {
            "type": "PartialSyncError",
            "message": (
                f"{report.failed} source file(s) failed; successfully indexed "
                "files were preserved"
            ),
        }
    if arguments.json_mode:
        _emit_json(payload)
    else:
        print(
            f"Indexed {report.indexed}, skipped {report.skipped}, "
            f"failed {report.failed}; {report.records_indexed} records updated."
        )
        if report.records_review_needed:
            print(
                f"{report.records_review_needed} updated records need review."
            )
    return 0 if report.failed == 0 else 1


def _run_search(arguments: argparse.Namespace) -> int:
    database = _database()
    encoder = (
        create_encoder(
            arguments.backend,
            model_name=arguments.model,
            dimensions=arguments.dimensions,
        )
        if arguments.semantic
        else None
    )
    results = search(
        database,
        arguments.query,
        course=arguments.course,
        source_file=arguments.source,
        ordinal=arguments.ordinal,
        limit=(
            arguments.limit
            if arguments.limit is not None
            else (8 if arguments.full else 6)
        ),
        encoder=encoder,
    )
    health = database.source_health(arguments.course)
    warnings = list(database.source_failures(arguments.course))
    warnings.extend(
        {
            "type": "extraction_review_needed",
            "course": result.course,
            "source_file": result.source_file,
            "ordinal": str(result.ordinal),
            "reasons": list(result.extraction_reasons),
            "message": "Returned evidence may have incomplete native extraction.",
        }
        for result in results
        if result.extraction_status == "review-needed"
    )
    message = None
    if not results:
        message = _empty_search_message(
            total_sources=health.total,
            failed_sources=health.failed,
        )
    elif health.failed:
        if any(result.source_status == "failed" for result in results):
            message = (
                "Some returned results come from sources whose latest refresh "
                "failed. Re-index the course before relying on them."
            )
        else:
            message = (
                "Other indexed sources failed their latest refresh; returned "
                "results are from ready sources. Inspect `classcorpus status` "
                "for missing coverage."
            )
    payload = search_response(
        results,
        warnings=warnings,
        sync_required=health.total == 0 or health.failed > 0,
        suggested_terms=(
            [] if results else suggest_terms(database, arguments.query)
        ),
        message=message,
        full=arguments.full,
        budget_tokens=arguments.budget_tokens,
        compact_option_used=arguments.compact,
    )
    payload_results = payload["results"]
    if arguments.json_mode:
        _emit_json(payload)
    elif results:
        for result in payload_results:
            title = result["title"] or "(untitled)"
            print(f"{result['citation']} {title}")
            print(f"  {result.get('snippet', result.get('evidence', ''))}")
    else:
        print(payload["message"])
        if payload["suggested_terms"]:
            print("Did you mean: " + ", ".join(payload["suggested_terms"]))
    return 0


def _run_outline(arguments: argparse.Namespace) -> int:
    payload = outline_course(
        _database(),
        course=arguments.course,
        source_file=arguments.source,
        cursor=arguments.cursor,
        budget_tokens=arguments.budget_tokens,
    )
    if arguments.json_mode:
        _emit_json(payload)
        return 0

    print(
        f"{payload['course']}: {payload['total_records']} records; "
        f"{payload['review_needed']} need review."
    )
    sources = payload["sources"]
    for group in payload["coverage"]:
        source = sources[group["source_id"]]["source_file"]
        start = group["start_ordinal"]
        end = group["end_ordinal"]
        span = str(start) if start == end else f"{start}-{end}"
        print(f"{source} {group['kind']} {span}: {group['title'] or '(untitled)'}")
    if payload["continuation"] is not None:
        print(f"Continue: {payload['continuation']['command']}")
    return 0


def _run_read(arguments: argparse.Namespace) -> int:
    chunk = read_record_text(
        _database(),
        course=arguments.course,
        source_file=arguments.source,
        ordinal=arguments.ordinal,
        field=arguments.field,
        offset=arguments.offset,
        limit=arguments.limit,
    )
    payload = {"ok": True, **asdict(chunk)}
    if arguments.json_mode:
        _emit_json(payload)
        return 0

    title = chunk.title or "(untitled)"
    print(f"{chunk.citation} {title}")
    print(chunk.text if chunk.text else f"(no text in {chunk.field})")
    end = chunk.offset + chunk.returned_chars
    print(f"\nCharacters {chunk.offset}-{end} of {chunk.total_chars}.")
    if chunk.next_offset is not None:
        command = shlex.join(
            [
                "classcorpus",
                "read",
                chunk.course,
                chunk.source_file,
                str(chunk.ordinal),
                "--field",
                chunk.field,
                "--offset",
                str(chunk.next_offset),
                "--limit",
                str(arguments.limit),
            ]
        )
        print(f"Continue: {command}")
    return 0


def _run_status(arguments: argparse.Namespace) -> int:
    report = status_report(_database(), course=arguments.course)
    if arguments.json_mode:
        _emit_json(report)
        return 0
    if not report["courses"]:
        print("No matching indexed courses.")
        for action in report["next_actions"]:
            print(f"Next: {action}")
        return 0
    for course in report["courses"]:
        print(
            f"{course['name']}: {course['records_total']} records from "
            f"{course['sources_total']} sources"
        )
        print(
            f"  sources ready/failed: {course['sources_ready']}/"
            f"{course['sources_failed']}; review needed: "
            f"{course['records_review_needed']}"
        )
        print(
            f"  OCR complete/failed: {course['ocr_complete']}/"
            f"{course['ocr_failed']}; embedded records: "
            f"{course['embedded_records']}"
        )
        for action in course["next_actions"]:
            print(f"  Next: {action}")
    return 0


def _run_doctor(arguments: argparse.Namespace) -> int:
    report = doctor_report()
    if arguments.json_mode:
        _emit_json(report)
    else:
        print(f"ClassCorpus {report['version']}")
        for check in report["checks"]:
            marker = "OK" if check["status"] == "pass" else check["status"].upper()
            print(f"[{marker}] {check['name']}: {check['message']}")
            if check["action"]:
                print(f"  {check['action']}")
        print("Core requirements are ready." if report["ok"] else "Core checks failed.")
    return 0 if report["ok"] else 1


def _database() -> Database:
    database = Database()
    database.initialize()
    return database


def _empty_search_message(*, total_sources: int, failed_sources: int) -> str:
    if total_sources == 0:
        return (
            "No indexed course evidence is available. Run "
            "`classcorpus index COURSE SOURCE_ROOT`."
        )
    if failed_sources:
        return (
            "No evidence matched and one or more sources failed their latest "
            "refresh. Re-index the course and inspect `classcorpus status`."
        )
    return "No indexed evidence matched. Try alternative terms or filters."


def _add_json_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", dest="json_mode")


def _emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True))


if __name__ == "__main__":
    raise SystemExit(main())
