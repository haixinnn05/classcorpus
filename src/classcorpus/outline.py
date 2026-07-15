from __future__ import annotations

import base64
import json
import re
import shlex
from typing import Any

from classcorpus.database import Database
from classcorpus.payloads import estimate_tokens, with_estimated_tokens

DEFAULT_OUTLINE_BUDGET_TOKENS = 1_500


def outline_course(
    database: Database,
    *,
    course: str,
    source_file: str | None = None,
    cursor: str | None = None,
    budget_tokens: int = DEFAULT_OUTLINE_BUDGET_TOKENS,
) -> dict[str, Any]:
    if budget_tokens < 1:
        raise ValueError("budget_tokens must be at least 1")
    continuation = (
        _decode_cursor(cursor, course=course, source_file=source_file)
        if cursor is not None
        else None
    )
    scope_clause = "courses.name = ?"
    scope_parameters: list[object] = [course]
    if source_file is not None:
        scope_clause += " AND source_files.relative_path = ?"
        scope_parameters.append(source_file)

    summary = database.connection.execute(
        f"""
        SELECT
            COUNT(*) AS total_records,
            COALESCE(SUM(slides.extraction_status = 'review-needed'), 0)
                AS review_needed
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE {scope_clause}
        """,
        scope_parameters,
    ).fetchone()

    page_clause = ""
    parameters = list(scope_parameters)
    if continuation is not None:
        page_clause = """
            AND (
                source_files.relative_path > ?
                OR (
                    source_files.relative_path = ?
                    AND slides.ordinal > ?
                )
            )
        """
        parameters.extend(
            [
                continuation[0],
                continuation[0],
                continuation[1],
            ]
        )
    rows = database.connection.execute(
        f"""
        SELECT
            courses.name AS course,
            source_files.relative_path AS source_file,
            source_files.source_path,
            source_files.status AS source_status,
            source_files.error_message AS source_error,
            slides.ordinal,
            slides.kind,
            slides.title,
            slides.extraction_status,
            slides.native_text_chars
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE {scope_clause}
        {page_clause}
        ORDER BY source_files.relative_path, slides.ordinal
        """,
        parameters,
    ).fetchall()
    groups = _group_rows(rows)
    warnings: list[dict[str, object]] = list(database.source_failures(course))
    review_needed = int(summary["review_needed"])
    if review_needed:
        warnings.append(
            {
                "type": "extraction_review_needed",
                "course": course,
                "source_file": source_file,
                "records": review_needed,
                "message": "The requested scope contains records needing review.",
            }
        )

    payload: dict[str, Any] = {
        "ok": True,
        "course": course,
        "scope_source": source_file,
        "sources": {},
        "coverage": [],
        "total_records": int(summary["total_records"]),
        "returned_records": 0,
        "remaining_records": int(summary["total_records"]),
        "review_needed": review_needed,
        "warnings": warnings,
        "has_more": False,
        "next_cursor": None,
        "continuation": None,
        "budget_tokens": budget_tokens,
        "budget_exhausted": False,
    }
    source_ids: dict[tuple[object, ...], str] = {}
    visible_groups: list[dict[str, Any]] = []
    consumed_before = _count_before_cursor(
        database,
        course=course,
        source_file=source_file,
        continuation=continuation,
    )
    for index, group in enumerate(groups):
        candidate_sources = dict(payload["sources"])
        source_key = (
            group["source_file"],
            group["source_path"],
            group["source_status"],
            group["source_error"],
        )
        source_id = source_ids.get(source_key)
        if source_id is None:
            source_id = f"s{len(source_ids) + 1}"
            candidate_sources[source_id] = {
                "source_file": group["source_file"],
                "source_path": group["source_path"],
                "source_status": group["source_status"],
                "source_error": group["source_error"],
            }
        candidate_group = _public_group(group, source_id=source_id)
        candidate_groups = [*visible_groups, candidate_group]
        candidate_returned = sum(
            int(item["record_count"]) for item in candidate_groups
        )
        candidate_represented = consumed_before + candidate_returned
        candidate_has_more = index < len(groups) - 1
        candidate_cursor = (
            _encode_cursor(
                course=course,
                scope_source=source_file,
                source_file=str(group["source_file"]),
                ordinal=int(group["end_ordinal"]),
            )
            if candidate_has_more
            else None
        )
        candidate_payload = {
            **payload,
            "sources": candidate_sources,
            "coverage": candidate_groups,
            "returned_records": candidate_returned,
            "remaining_records": max(
                0,
                int(summary["total_records"]) - candidate_represented,
            ),
            "has_more": candidate_has_more,
            "next_cursor": candidate_cursor,
            "continuation": (
                {
                    "cursor": candidate_cursor,
                    "command": _continuation_command(
                        course=course,
                        source_file=source_file,
                        cursor=candidate_cursor,
                        budget_tokens=budget_tokens,
                    ),
                }
                if candidate_cursor is not None
                else None
            ),
            "budget_exhausted": candidate_has_more,
        }
        if (
            visible_groups
            and estimate_tokens({**candidate_payload, "estimated_tokens": 0})
            > budget_tokens
        ):
            break
        if source_key not in source_ids:
            source_ids[source_key] = source_id
            payload["sources"] = candidate_sources
        visible_groups.append(candidate_group)

    returned_records = sum(
        int(group["record_count"]) for group in visible_groups
    )
    represented = consumed_before + returned_records
    has_more = represented < int(summary["total_records"])
    next_cursor = None
    if has_more and visible_groups:
        last = visible_groups[-1]
        source = payload["sources"][last["source_id"]]["source_file"]
        next_cursor = _encode_cursor(
            course=course,
            scope_source=source_file,
            source_file=str(source),
            ordinal=int(last["end_ordinal"]),
        )
    payload.update(
        {
            "coverage": visible_groups,
            "returned_records": returned_records,
            "remaining_records": max(
                0,
                int(summary["total_records"]) - represented,
            ),
            "has_more": has_more,
            "next_cursor": next_cursor,
            "continuation": (
                {
                    "cursor": next_cursor,
                    "command": _continuation_command(
                        course=course,
                        source_file=source_file,
                        cursor=next_cursor,
                        budget_tokens=budget_tokens,
                    ),
                }
                if next_cursor is not None
                else None
            ),
            "budget_exhausted": has_more,
        }
    )
    if estimate_tokens({**payload, "estimated_tokens": 0}) > budget_tokens:
        payload["budget_exhausted"] = True
    return with_estimated_tokens(payload)


def _group_rows(rows) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for row in rows:
        key = (
            str(row["source_file"]),
            str(row["kind"]),
            _normalize_title(str(row["title"])),
        )
        if groups and groups[-1]["key"] == key:
            group = groups[-1]
            group["end_ordinal"] = int(row["ordinal"])
            group["record_count"] += 1
            group["review_needed"] += (
                str(row["extraction_status"]) == "review-needed"
            )
            group["native_text_chars"] += int(row["native_text_chars"])
            continue
        groups.append(
            {
                "key": key,
                "course": str(row["course"]),
                "source_file": str(row["source_file"]),
                "source_path": str(row["source_path"]),
                "source_status": str(row["source_status"]),
                "source_error": (
                    str(row["source_error"])
                    if row["source_error"] is not None
                    else None
                ),
                "start_ordinal": int(row["ordinal"]),
                "end_ordinal": int(row["ordinal"]),
                "record_count": 1,
                "kind": str(row["kind"]),
                "title": str(row["title"]),
                "review_needed": int(
                    str(row["extraction_status"]) == "review-needed"
                ),
                "native_text_chars": int(row["native_text_chars"]),
            }
        )
    return groups


def _public_group(group: dict[str, Any], *, source_id: str) -> dict[str, Any]:
    label = "Slide" if group["kind"] == "slide" else "Page"
    start = int(group["start_ordinal"])
    end = int(group["end_ordinal"])
    citation_start = (
        f"[{group['course']}, {group['source_file']}, {label} {start}]"
    )
    citation_end = (
        f"[{group['course']}, {group['source_file']}, {label} {end}]"
    )
    return {
        "source_id": source_id,
        "start_ordinal": start,
        "end_ordinal": end,
        "record_count": int(group["record_count"]),
        "kind": group["kind"],
        "title": group["title"],
        "review_needed": int(group["review_needed"]),
        "native_text_chars": int(group["native_text_chars"]),
        "citation_start": citation_start,
        "citation_end": citation_end,
        "read": {
            "source_id": source_id,
            "start_ordinal": start,
            "end_ordinal": end,
            "field": "searchable",
        },
    }


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().casefold()


def _count_before_cursor(
    database: Database,
    *,
    course: str,
    source_file: str | None,
    continuation: tuple[str, int] | None,
) -> int:
    if continuation is None:
        return 0
    clauses = ["courses.name = ?"]
    parameters: list[object] = [course]
    if source_file is not None:
        clauses.append("source_files.relative_path = ?")
        parameters.append(source_file)
    clauses.append(
        """
        (
            source_files.relative_path < ?
            OR (
                source_files.relative_path = ?
                AND slides.ordinal <= ?
            )
        )
        """
    )
    parameters.extend([continuation[0], continuation[0], continuation[1]])
    row = database.connection.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE {" AND ".join(clauses)}
        """,
        parameters,
    ).fetchone()
    return int(row["count"])


def _encode_cursor(
    *,
    course: str,
    scope_source: str | None,
    source_file: str,
    ordinal: int,
) -> str:
    payload = json.dumps(
        {
            "course": course,
            "scope_source": scope_source,
            "source_file": source_file,
            "ordinal": ordinal,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(
    cursor: str,
    *,
    course: str,
    source_file: str | None,
) -> tuple[str, int]:
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = base64.b64decode(
            cursor + padding,
            altchars=b"-_",
            validate=True,
        )
        value = json.loads(payload.decode("utf-8"))
        if (
            not isinstance(value, dict)
            or set(value)
            != {"course", "scope_source", "source_file", "ordinal"}
            or value["course"] != course
            or value["scope_source"] != source_file
            or not isinstance(value["source_file"], str)
            or not value["source_file"]
            or not isinstance(value["ordinal"], int)
            or isinstance(value["ordinal"], bool)
            or value["ordinal"] < 1
        ):
            raise ValueError
    except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("cursor is malformed or belongs to another scope") from error
    return value["source_file"], value["ordinal"]


def _continuation_command(
    *,
    course: str,
    source_file: str | None,
    cursor: str,
    budget_tokens: int,
) -> str:
    arguments = [
        "classcorpus",
        "outline",
        course,
        "--cursor",
        cursor,
        "--budget-tokens",
        str(budget_tokens),
    ]
    if source_file is not None:
        arguments.extend(["--source", source_file])
    arguments.append("--json")
    return shlex.join(arguments)


__all__ = ["DEFAULT_OUTLINE_BUDGET_TOKENS", "outline_course"]
