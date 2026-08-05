from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from classcorpus.citations import format_record_citation
from classcorpus.database import Database
from classcorpus.flashcards import Flashcard
from classcorpus.security import mark_untrusted_content

RATING_AGAIN = "again"
RATING_HARD = "hard"
RATING_GOOD = "good"
RATING_EASY = "easy"
RATINGS = (RATING_AGAIN, RATING_HARD, RATING_GOOD, RATING_EASY)
PROGRESS_FORMAT = "classcorpus-study-progress"
PROGRESS_VERSION = 1


@dataclass(frozen=True, slots=True)
class CardIdentity:
    card_id: str
    card_key: str
    source_sha256: str
    citation: str


def identify_cards(
    database: Database,
    cards: Sequence[Flashcard],
) -> list[CardIdentity]:
    citation_hashes = _citation_hashes(database)
    return [
        identify_card_content(
            card,
            source_sha256=citation_hashes.get(card.citation.strip(), ""),
        )
        for card in cards
    ]


def identify_card_content(
    card: Flashcard,
    *,
    source_sha256: str = "",
) -> CardIdentity:
    citation = card.citation.strip()
    card_key = _digest(
        {
            "front": _normalize(card.front),
            "back": _normalize(card.back),
            "citation": citation,
        }
    )
    card_id = _digest({"card_key": card_key, "source_sha256": source_sha256})
    return CardIdentity(
        card_id=card_id,
        card_key=card_key,
        source_sha256=source_sha256,
        citation=citation,
    )


def deck_progress(
    database: Database,
    cards: Sequence[Flashcard],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = _aware_utc(now or datetime.now(timezone.utc))
    identities = identify_cards(database, cards)
    results: list[dict[str, Any]] = []
    counts = {"new": 0, "due": 0, "future": 0, "stale": 0}
    for card, identity in zip(cards, identities, strict=True):
        row = database.connection.execute(
            "SELECT * FROM flashcard_reviews WHERE card_id = ?",
            (identity.card_id,),
        ).fetchone()
        previous = None
        if row is None:
            previous = database.connection.execute(
                """
                SELECT * FROM flashcard_reviews
                WHERE card_key = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (identity.card_key,),
            ).fetchone()
        if row is not None:
            due_at = _parse_time(str(row["due_at"]))
            status = "due" if due_at <= current_time else "future"
        elif previous is not None:
            status = "stale"
        else:
            status = "new"
        counts[status] += 1
        review_row = row if row is not None else previous
        results.append(
            {
                **asdict(identity),
                "front": card.front,
                "tags": list(card.tags),
                "status": status,
                "previous_card_id": (
                    str(previous["card_id"]) if previous is not None else None
                ),
                "repetitions": (
                    int(review_row["repetitions"]) if review_row is not None else 0
                ),
                "lapses": int(review_row["lapses"]) if review_row is not None else 0,
                "interval_days": (
                    float(review_row["interval_days"])
                    if review_row is not None
                    else 0.0
                ),
                "ease": float(review_row["ease"]) if review_row is not None else 2.5,
                "due_at": str(review_row["due_at"]) if review_row is not None else None,
                "last_reviewed_at": (
                    str(review_row["last_reviewed_at"])
                    if review_row is not None
                    else None
                ),
            }
        )
    payload: dict[str, Any] = {
        "ok": True,
        "as_of": current_time.isoformat(),
        "summary": {"cards": len(cards), **counts},
        "cards": results,
        "method": (
            "Deterministic local SM-2-inspired scheduling. Progress is not a "
            "claim of mastery."
        ),
    }
    return mark_untrusted_content(payload)


def record_review(
    database: Database,
    cards: Sequence[Flashcard],
    *,
    card_id: str,
    rating: str,
    confidence: int | None = None,
    reviewed_at: datetime | None = None,
) -> dict[str, Any]:
    if rating not in RATINGS:
        raise ValueError("rating must be again, hard, good, or easy")
    if confidence is not None and not 1 <= confidence <= 5:
        raise ValueError("confidence must be between 1 and 5")
    identities = identify_cards(database, cards)
    identity = next((item for item in identities if item.card_id == card_id), None)
    if identity is None:
        raise ValueError("card id is not present in the current deck")
    current_time = _aware_utc(reviewed_at or datetime.now(timezone.utc))
    row = database.connection.execute(
        "SELECT * FROM flashcard_reviews WHERE card_id = ?",
        (card_id,),
    ).fetchone()
    repetitions = int(row["repetitions"]) if row is not None else 0
    lapses = int(row["lapses"]) if row is not None else 0
    interval = float(row["interval_days"]) if row is not None else 0.0
    ease = float(row["ease"]) if row is not None else 2.5
    previous_due_at = str(row["due_at"]) if row is not None else None

    repetitions, lapses, interval, ease = _schedule(
        rating,
        repetitions=repetitions,
        lapses=lapses,
        interval_days=interval,
        ease=ease,
    )
    due_at = current_time + timedelta(days=interval)
    now_text = current_time.isoformat()
    due_text = due_at.isoformat()
    created_at = str(row["created_at"]) if row is not None else now_text
    with database.connection:
        database.connection.execute(
            """
            INSERT INTO flashcard_reviews(
                card_id, card_key, source_sha256, citation, repetitions,
                lapses, interval_days, ease, due_at, last_reviewed_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(card_id) DO UPDATE SET
                repetitions = excluded.repetitions,
                lapses = excluded.lapses,
                interval_days = excluded.interval_days,
                ease = excluded.ease,
                due_at = excluded.due_at,
                last_reviewed_at = excluded.last_reviewed_at,
                updated_at = excluded.updated_at
            """,
            (
                identity.card_id,
                identity.card_key,
                identity.source_sha256,
                identity.citation,
                repetitions,
                lapses,
                interval,
                ease,
                due_text,
                now_text,
                created_at,
                now_text,
            ),
        )
        database.connection.execute(
            """
            INSERT OR IGNORE INTO flashcard_review_events(
                card_id, rating, confidence, reviewed_at,
                previous_due_at, new_due_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                card_id,
                rating,
                confidence,
                now_text,
                previous_due_at,
                due_text,
            ),
        )
    return {
        "ok": True,
        **asdict(identity),
        "rating": rating,
        "confidence": confidence,
        "repetitions": repetitions,
        "lapses": lapses,
        "interval_days": interval,
        "ease": ease,
        "due_at": due_text,
        "last_reviewed_at": now_text,
    }


def export_progress(
    database: Database,
    cards: Sequence[Flashcard],
    output: Path,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    output = output.expanduser().resolve()
    if output.exists() and not overwrite:
        raise FileExistsError(
            f"output already exists: {output}; pass --overwrite to replace it"
        )
    identities = identify_cards(database, cards)
    keys = [identity.card_key for identity in identities]
    reviews = _rows_for_keys(database, "flashcard_reviews", keys)
    card_ids = [str(row["card_id"]) for row in reviews]
    events = _events_for_cards(database, card_ids)
    payload = {
        "format": PROGRESS_FORMAT,
        "version": PROGRESS_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "reviews": reviews,
        "events": events,
    }
    _write_json_atomic(output, payload)
    return {
        "ok": True,
        "output": str(output),
        "reviews": len(reviews),
        "events": len(events),
    }


def import_progress(database: Database, source: Path) -> dict[str, Any]:
    payload = json.loads(source.expanduser().read_text(encoding="utf-8"))
    if payload.get("format") != PROGRESS_FORMAT or payload.get("version") != 1:
        raise ValueError("unsupported ClassCorpus study progress file")
    reviews = payload.get("reviews")
    events = payload.get("events")
    if not isinstance(reviews, list) or not isinstance(events, list):
        raise ValueError("study progress reviews and events must be arrays")
    with database.connection:
        for review in reviews:
            _import_review(database, review)
        for event in events:
            _import_event(database, event)
    return {"ok": True, "reviews": len(reviews), "events": len(events)}


def _schedule(
    rating: str,
    *,
    repetitions: int,
    lapses: int,
    interval_days: float,
    ease: float,
) -> tuple[int, int, float, float]:
    if rating == RATING_AGAIN:
        return 0, lapses + 1, 10 / 1440, max(1.3, ease - 0.2)
    if rating == RATING_HARD:
        return (
            repetitions + 1,
            lapses,
            max(1.0, interval_days * 1.2),
            max(1.3, ease - 0.15),
        )
    if rating == RATING_GOOD:
        if repetitions == 0:
            interval = 1.0
        elif repetitions == 1:
            interval = 6.0
        else:
            interval = max(interval_days + 1, round(interval_days * ease, 1))
        return repetitions + 1, lapses, interval, ease
    if repetitions == 0:
        interval = 4.0
    elif repetitions == 1:
        interval = 7.0
    else:
        interval = max(interval_days + 2, round(interval_days * (ease + 0.3), 1))
    return repetitions + 1, lapses, interval, ease + 0.15


def _citation_hashes(database: Database) -> dict[str, str]:
    rows = database.connection.execute(
        """
        SELECT courses.name AS course, source_files.relative_path,
               source_files.sha256, slides.ordinal, slides.kind, slides.start_ms
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        """
    ).fetchall()
    values: dict[str, str] = {}
    for row in rows:
        citation = format_record_citation(
            course=str(row["course"]),
            source_file=str(row["relative_path"]),
            kind=str(row["kind"]),
            ordinal=int(row["ordinal"]),
            start_ms=(int(row["start_ms"]) if row["start_ms"] is not None else None),
        )
        values[citation] = str(row["sha256"])
    return values


def _rows_for_keys(
    database: Database,
    table: str,
    keys: list[str],
) -> list[dict[str, Any]]:
    if not keys:
        return []
    placeholders = ",".join("?" for _ in keys)
    rows = database.connection.execute(
        f"SELECT * FROM {table} WHERE card_key IN ({placeholders}) "
        "ORDER BY card_key, updated_at",
        keys,
    ).fetchall()
    return [dict(row) for row in rows]


def _events_for_cards(
    database: Database,
    card_ids: list[str],
) -> list[dict[str, Any]]:
    if not card_ids:
        return []
    placeholders = ",".join("?" for _ in card_ids)
    rows = database.connection.execute(
        "SELECT card_id, rating, confidence, reviewed_at, previous_due_at, "
        f"new_due_at FROM flashcard_review_events WHERE card_id IN ({placeholders}) "
        "ORDER BY reviewed_at, id",
        card_ids,
    ).fetchall()
    return [dict(row) for row in rows]


def _import_review(database: Database, value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("study progress review must be an object")
    fields = (
        "card_id",
        "card_key",
        "source_sha256",
        "citation",
        "repetitions",
        "lapses",
        "interval_days",
        "ease",
        "due_at",
        "last_reviewed_at",
        "created_at",
        "updated_at",
    )
    if any(field not in value for field in fields):
        raise ValueError("study progress review is missing required fields")
    database.connection.execute(
        """
        INSERT INTO flashcard_reviews(
            card_id, card_key, source_sha256, citation, repetitions, lapses,
            interval_days, ease, due_at, last_reviewed_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(card_id) DO UPDATE SET
            repetitions = excluded.repetitions,
            lapses = excluded.lapses,
            interval_days = excluded.interval_days,
            ease = excluded.ease,
            due_at = excluded.due_at,
            last_reviewed_at = excluded.last_reviewed_at,
            updated_at = excluded.updated_at
        WHERE excluded.updated_at >= flashcard_reviews.updated_at
        """,
        tuple(value[field] for field in fields),
    )


def _import_event(database: Database, value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError("study progress event must be an object")
    fields = (
        "card_id",
        "rating",
        "confidence",
        "reviewed_at",
        "previous_due_at",
        "new_due_at",
    )
    if any(field not in value for field in fields):
        raise ValueError("study progress event is missing required fields")
    database.connection.execute(
        """
        INSERT OR IGNORE INTO flashcard_review_events(
            card_id, rating, confidence, reviewed_at, previous_due_at, new_due_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        tuple(value[field] for field in fields),
    )


def _normalize(value: str) -> str:
    return " ".join(value.split())


def _digest(value: dict[str, str]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("review timestamps must include a timezone")
    return value.astimezone(timezone.utc)


def _parse_time(value: str) -> datetime:
    return _aware_utc(datetime.fromisoformat(value))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


__all__ = [
    "RATING_AGAIN",
    "RATING_EASY",
    "RATING_GOOD",
    "RATING_HARD",
    "CardIdentity",
    "deck_progress",
    "export_progress",
    "identify_card_content",
    "identify_cards",
    "import_progress",
    "record_review",
]
