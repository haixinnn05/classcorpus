#!/usr/bin/env python3
from __future__ import annotations

from _common import argument_parser, emit, fail
from _embeddings import create_encoder
from classcorpus.database import Database
from classcorpus.payloads import (
    DEFAULT_SEARCH_BUDGET_TOKENS,
    search_response,
)
from classcorpus.search import search, suggest_terms


def main() -> int:
    parser = argument_parser(description="Search indexed course materials.")
    parser.add_argument("query")
    parser.add_argument("--course")
    parser.add_argument("--source")
    parser.add_argument("--ordinal", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--semantic", action="store_true")
    parser.add_argument(
        "--backend",
        choices=("sentence-transformers", "fastembed", "hashing"),
        default="sentence-transformers",
    )
    parser.add_argument("--model")
    parser.add_argument("--dimensions", type=int, default=384)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument(
        "--budget-tokens",
        type=int,
        default=DEFAULT_SEARCH_BUDGET_TOKENS,
    )
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
            limit=(
                args.limit
                if args.limit is not None
                else (8 if args.full else 6)
            ),
            encoder=encoder,
        )
        health = database.source_health(args.course)
        warnings = list(database.source_failures(args.course))
        warnings.extend(
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
        message = _message(results, total=health.total, failed=health.failed)
        response = search_response(
            results,
            warnings=warnings,
            sync_required=health.total == 0 or health.failed > 0,
            suggested_terms=(
                [] if results else suggest_terms(database, args.query)
            ),
            message=message,
            full=args.full,
            budget_tokens=args.budget_tokens,
            compact_option_used=args.compact,
        )
        emit(response, json_mode=args.json_mode)
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


def _message(results, *, total: int, failed: int) -> str | None:
    if not results:
        if total == 0:
            return (
                "No indexed course evidence is available. Synchronize the "
                "course with index_lectures.py."
            )
        if failed:
            return (
                "No evidence matched and one or more sources failed their "
                "latest refresh. Synchronize the course and inspect warnings."
            )
        return (
            "No indexed evidence matched. Search with alternative terms or "
            "adjust the source and ordinal filters."
        )
    if failed and any(result.source_status == "failed" for result in results):
        return (
            "Some returned results come from sources whose latest refresh "
            "failed. Synchronize the course and inspect warnings before "
            "relying on them."
        )
    if failed:
        return (
            "Other indexed sources failed their latest refresh; returned "
            "results are from ready sources. Synchronize the course and "
            "inspect warnings for missing coverage."
        )
    return None


if __name__ == "__main__":
    raise SystemExit(main())
