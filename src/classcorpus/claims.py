"""Check whether cited claims are supported by the records they cite.

`verify_artifact` answers whether a cited source still matches what was indexed.
This module answers a different question: does the cited record actually say what
the claim says? An agent can write a well-formed citation onto a fabricated
number, and every hash check will still pass.

The check is lexical and local, so it is a support signal rather than proof of
entailment. A paraphrase can score low without being wrong. Measurements, meaning
complexity expressions, powers, and numbers, are treated separately and strictly,
because that is where fabrication is both most damaging and most detectable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any

from classcorpus.database import Database
from classcorpus.provenance import CITATION_PATTERN
from classcorpus.record_text import (
    RECORD_TEXT_FIELDS,
    RecordTextField,
    read_record_text,
)
from classcorpus.security import mark_untrusted_content

DEFAULT_SUPPORT_THRESHOLD = 0.6
MAX_RECORD_CHARS = 50_000

VERDICT_SUPPORTED = "supported"
VERDICT_WEAK = "weak"
VERDICT_UNSUPPORTED = "unsupported"
VERDICT_UNVERIFIED = "unverified"

_CITATION_PARTS = re.compile(
    r"\[(?P<course>[^,\]]+),\s*(?P<source>[^,\]]+),\s*"
    r"(?P<label>Slide|Page)\s+(?P<ordinal>\d+)\]"
)
_MEASUREMENT_PATTERNS = (
    # Complexity classes, including the Greek forms a renderer may produce.
    re.compile(r"(?:O|o|Theta|Omega|Θ|Ω)\s*\([^)]{1,60}\)"),
    # Powers such as n^2 or n^{log_b(a)}.
    re.compile(r"[A-Za-z](?:\^\{[^}]{1,40}\}|\^[A-Za-z0-9()+\-*/_]{1,20})"),
    # Bare numbers, which is where invented constants appear.
    re.compile(r"\d+(?:\.\d+)?"),
)
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_STOPWORDS = frozenset(
    """
    a an and are as at be been but by can cannot could did do does for from
    had has have how if in into is it its may might must no not of on one only
    or over should so some such than that the their then there these they this
    those to use used uses using was were what when where which while who why
    will with would you your it's
    """.split()
)


@dataclass(frozen=True, slots=True)
class ClaimCheck:
    claim: str
    line: int
    citation: str
    verdict: str
    support: float
    missing_terms: tuple[str, ...]
    missing_measurements: tuple[str, ...]
    message: str


def check_claims(
    database: Database,
    source: Path,
    *,
    field: RecordTextField = "searchable",
    threshold: float = DEFAULT_SUPPORT_THRESHOLD,
) -> dict[str, Any]:
    """Score every cited claim in a Markdown or text artifact source."""
    if field not in RECORD_TEXT_FIELDS:
        raise ValueError(f"unknown field: {field}")
    if not 0 < threshold <= 1:
        raise ValueError("threshold must be greater than 0 and at most 1")
    if not source.is_file():
        raise FileNotFoundError(f"citation source not found: {source}")

    text = source.read_text(encoding="utf-8")
    record_cache: dict[str, str | None] = {}
    checks = [
        _check_one(database, claim, line, citation, field, threshold, record_cache)
        for claim, line, citation in _cited_claims(text)
    ]

    counts = {
        verdict: sum(1 for check in checks if check.verdict == verdict)
        for verdict in (
            VERDICT_SUPPORTED,
            VERDICT_WEAK,
            VERDICT_UNSUPPORTED,
            VERDICT_UNVERIFIED,
        )
    }
    payload: dict[str, Any] = {
        "ok": counts[VERDICT_UNSUPPORTED] == 0 and counts[VERDICT_UNVERIFIED] == 0,
        "source": str(source),
        "field": field,
        "threshold": threshold,
        "claims_total": len(checks),
        "counts": counts,
        "claims": [_claim_payload(check) for check in checks],
        "method": (
            "Lexical support signal, not proof of entailment. A paraphrase can "
            "score low without being wrong; review flagged claims against the "
            "cited record."
        ),
    }
    if not checks:
        payload["message"] = (
            "No citations found. Claims must cite records as "
            "[Course, source, Page N]."
        )
    mark_untrusted_content(payload)
    return payload


def _claim_payload(check: ClaimCheck) -> dict[str, Any]:
    """Emit JSON-shaped values so the payload is identical before serialization."""
    payload = asdict(check)
    payload["missing_terms"] = list(check.missing_terms)
    payload["missing_measurements"] = list(check.missing_measurements)
    return payload


def _cited_claims(text: str) -> list[tuple[str, int, str]]:
    """Return (claim, line, citation) triples, one per citation.

    A claim is the sentence, list item, or table row carrying the citation, so a
    paragraph citing three records yields three separately checkable claims.
    """
    triples: list[tuple[str, int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not CITATION_PATTERN.search(line):
            continue
        for unit in _claim_units(line):
            for citation in CITATION_PATTERN.findall(unit):
                triples.append((unit.strip(), number, citation))
    return triples


def _claim_units(line: str) -> list[str]:
    body = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", line).strip()
    body = body.strip("|").strip() if body.startswith("|") else body
    units = [unit.strip() for unit in _SENTENCE_BOUNDARY.split(body)]
    return [unit for unit in units if unit]


def _check_one(
    database: Database,
    claim: str,
    line: int,
    citation: str,
    field: RecordTextField,
    threshold: float,
    record_cache: dict[str, str | None],
) -> ClaimCheck:
    record = _record_text(database, citation, field, record_cache)
    if record is None:
        return ClaimCheck(
            claim=claim,
            line=line,
            citation=citation,
            verdict=VERDICT_UNVERIFIED,
            support=0.0,
            missing_terms=(),
            missing_measurements=(),
            message=(
                "The cited record is not indexed. Synchronize the course, or "
                "correct the citation."
            ),
        )

    prose = _claim_prose(claim)
    haystack = _canonical(record)
    terms = _content_terms(prose)
    measurements = _measurements(prose)
    missing_terms = tuple(
        term for term in terms if not _contains_term(haystack, term)
    )
    missing_measurements = tuple(
        value
        for value in measurements
        if _canonical(value) not in haystack
    )
    support = (
        1.0 if not terms else (len(terms) - len(missing_terms)) / len(terms)
    )

    if missing_measurements:
        return ClaimCheck(
            claim=claim,
            line=line,
            citation=citation,
            verdict=VERDICT_UNSUPPORTED,
            support=round(support, 3),
            missing_terms=missing_terms,
            missing_measurements=missing_measurements,
            message=(
                "The cited record does not contain "
                f"{', '.join(missing_measurements)}. Verify the value against "
                "the source before publishing this claim."
            ),
        )
    if support < threshold:
        return ClaimCheck(
            claim=claim,
            line=line,
            citation=citation,
            verdict=VERDICT_WEAK,
            support=round(support, 3),
            missing_terms=missing_terms,
            missing_measurements=(),
            message=(
                "Little of this claim's wording appears in the cited record. "
                "It may be a paraphrase, a synthesis of several records, or the "
                "wrong citation."
            ),
        )
    return ClaimCheck(
        claim=claim,
        line=line,
        citation=citation,
        verdict=VERDICT_SUPPORTED,
        support=round(support, 3),
        missing_terms=missing_terms,
        missing_measurements=(),
        message="The cited record contains this claim's terms and measurements.",
    )


def _record_text(
    database: Database,
    citation: str,
    field: RecordTextField,
    cache: dict[str, str | None],
) -> str | None:
    if citation in cache:
        return cache[citation]
    parts = _CITATION_PARTS.fullmatch(citation.strip())
    if parts is None:
        cache[citation] = None
        return None
    try:
        chunk = read_record_text(
            database,
            course=parts.group("course").strip(),
            source_file=parts.group("source").strip(),
            ordinal=int(parts.group("ordinal")),
            field=field,
            offset=0,
            limit=MAX_RECORD_CHARS,
        )
    except Exception:
        cache[citation] = None
        return None
    cache[citation] = chunk.text
    return chunk.text


def _claim_prose(claim: str) -> str:
    """Strip citations and Markdown decoration, keeping the assertion itself."""
    value = CITATION_PATTERN.sub(" ", claim)
    value = re.sub(r"`([^`]*)`", r"\1", value)
    value = re.sub(r"\*\*([^*]*)\*\*", r"\1", value)
    value = re.sub(r"^#+\s*", "", value)
    return value.strip()


def _content_terms(prose: str) -> tuple[str, ...]:
    words = re.findall(r"[A-Za-z][A-Za-z'\-]{2,}", prose)
    terms: list[str] = []
    for word in words:
        lowered = word.lower().strip("-'")
        if len(lowered) < 3 or lowered in _STOPWORDS:
            continue
        if lowered not in terms:
            terms.append(lowered)
    return tuple(terms)


def _measurements(prose: str) -> tuple[str, ...]:
    found: list[str] = []
    remaining = prose
    for pattern in _MEASUREMENT_PATTERNS:
        for match in pattern.findall(remaining):
            value = match.strip()
            if value and value not in found:
                found.append(value)
        # Remove matches so a number inside O(n^2) is not also counted alone.
        remaining = pattern.sub(" ", remaining)
    return tuple(found)


def _contains_term(haystack: str, term: str) -> bool:
    """Match a term against canonicalized record text, tolerating plurals."""
    candidates = {term, term.rstrip("s"), f"{term}s"}
    if term.endswith("y"):
        candidates.add(f"{term[:-1]}ies")
    return any(_canonical(candidate) in haystack for candidate in candidates)


def _canonical(value: str) -> str:
    """Lowercase and drop whitespace so `O(V * E)` matches `O(V*E)`."""
    return re.sub(r"\s+", "", value).lower()


__all__ = [
    "DEFAULT_SUPPORT_THRESHOLD",
    "VERDICT_SUPPORTED",
    "VERDICT_UNSUPPORTED",
    "VERDICT_UNVERIFIED",
    "VERDICT_WEAK",
    "ClaimCheck",
    "check_claims",
]
