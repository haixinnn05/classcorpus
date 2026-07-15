#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict

from _common import argument_parser, emit, fail
from _embeddings import create_encoder
from classcorpus.citations import format_citation
from classcorpus.database import Database
from classcorpus.payloads import compact_search_result
from classcorpus.search import search, suggest_terms


def main() -> int:
    parser = argument_parser(description="Search indexed course materials.")
    parser.add_argument("query")
    parser.add_argument("--course")
    parser.add_argument("--source")
    parser.add_argument("--ordinal", type=int)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--semantic", action="store_true")
    parser.add_argument(
        "--backend",
        choices=("sentence-transformers", "fastembed", "hashing"),
        default="sentence-transformers",
    )
    parser.add_argument("--model")
    parser.add_argument("--dimensions", type=int, default=384)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        database = Database()
        database.initialize()
        encoder = (
            create_encoder(
                args.backend,
                model_name=args.model,
                dimensions=args.dimensions,
            )
            if args.semantic
            else None
        )
        results = search(
            database,
            args.query,
            course=args.course,
            source_file=args.source,
            ordinal=args.ordinal,
            limit=args.limit,
            encoder=encoder,
        )
        payload = (
            [compact_search_result(result) for result in results]
            if args.compact
            else [
                {**asdict(result), "citation": format_citation(result)}
                for result in results
            ]
        )
        health = database.source_health(args.course)
        source_warnings = list(database.source_failures(args.course))
        source_warnings.extend(
            {
                "type": "extraction_review_needed",
                "course": result.course,
                "source_file": result.source_file,
                "ordinal": str(result.ordinal),
                "reasons": list(result.extraction_reasons),
                "message": (
                    "Returned evidence may have incomplete native extraction."
                ),
            }
            for result in results
            if result.extraction_status == "review-needed"
        )
        sync_required = health.total == 0 or health.failed > 0
        response = {
            "ok": True,
            "results": payload,
            "sync_required": sync_required,
            "warnings": source_warnings,
            "compact": args.compact,
            "omitted_content_chars": (
                sum(int(item["omitted_content_chars"]) for item in payload)
                if args.compact
                else 0
            ),
            "suggested_terms": (
                [] if payload else suggest_terms(database, args.query)
            ),
        }
        if not payload:
            if health.total == 0:
                response["message"] = (
                    "No indexed course evidence is available. Synchronize the "
                    "course with index_lectures.py."
                )
            elif health.failed > 0:
                response["message"] = (
                    "No evidence matched and one or more sources failed their "
                    "latest refresh. Synchronize the course and inspect warnings."
                )
            else:
                response["message"] = (
                    "No indexed evidence matched. Search with alternative terms "
                    "or adjust the source and ordinal filters."
                )
        elif health.failed > 0:
            if any(result.source_status == "failed" for result in results):
                response["message"] = (
                    "Some returned results come from sources whose latest refresh "
                    "failed. Synchronize the course and inspect warnings before "
                    "relying on them."
                )
            else:
                response["message"] = (
                    "Other indexed sources failed their latest refresh; returned "
                    "results are from ready sources. Synchronize the course and "
                    "inspect warnings for missing coverage."
                )
        emit(response, json_mode=args.json_mode)
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
