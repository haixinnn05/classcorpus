from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any

from classcorpus.citations import format_citation
from classcorpus.database import Database
from classcorpus.diagnostics import doctor_report
from classcorpus.encoders import create_encoder
from classcorpus.indexer import sync_course
from classcorpus.search import search
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
    search_parser.add_argument("--limit", type=int, default=8)
    search_parser.add_argument("--semantic", action="store_true")
    search_parser.add_argument(
        "--backend",
        choices=("sentence-transformers", "fastembed", "hashing"),
        default="sentence-transformers",
    )
    search_parser.add_argument("--model")
    search_parser.add_argument("--dimensions", type=int, default=384)
    _add_json_argument(search_parser)
    search_parser.set_defaults(handler=_run_search)

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
        limit=arguments.limit,
        encoder=encoder,
    )
    payload_results = [
        {**asdict(result), "citation": format_citation(result)}
        for result in results
    ]
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
    payload: dict[str, Any] = {
        "ok": True,
        "results": payload_results,
        "sync_required": health.total == 0 or health.failed > 0,
        "warnings": warnings,
    }
    if not results:
        payload["message"] = _empty_search_message(
            total_sources=health.total,
            failed_sources=health.failed,
        )
    elif health.failed:
        if any(result.source_status == "failed" for result in results):
            payload["message"] = (
                "Some returned results come from sources whose latest refresh "
                "failed. Re-index the course before relying on them."
            )
        else:
            payload["message"] = (
                "Other indexed sources failed their latest refresh; returned "
                "results are from ready sources. Inspect `classcorpus status` "
                "for missing coverage."
            )
    if arguments.json_mode:
        _emit_json(payload)
    elif results:
        for result in payload_results:
            title = result["title"] or "(untitled)"
            print(f"{result['citation']} {title}")
            print(f"  {result['snippet']}")
    else:
        print(payload["message"])
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
