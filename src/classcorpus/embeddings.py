from __future__ import annotations

import math
from array import array
from typing import Protocol, Sequence

from classcorpus.database import Database


class Encoder(Protocol):
    model_name: str

    def encode(self, texts: list[str]) -> Sequence[Sequence[float]]: ...


def _searchable_text(row) -> str:
    return "\n".join(
        value
        for value in (
            row["title"],
            row["body_text"],
            row["speaker_notes"],
            row["visual_description"],
            row["ocr_text"],
        )
        if value
    )


def _normalize(values: Sequence[float]) -> list[float]:
    vector = [float(value) for value in values]
    magnitude = math.sqrt(sum(value * value for value in vector))
    if not vector or magnitude == 0:
        raise ValueError("embedding vector must be non-empty and non-zero")
    return [value / magnitude for value in vector]


def _encode_blob(values: Sequence[float]) -> tuple[int, bytes]:
    vector = array("f", _normalize(values))
    return len(vector), vector.tobytes()


def _decode_blob(blob: bytes, dimension: int) -> list[float]:
    vector = array("f")
    vector.frombytes(blob)
    if len(vector) != dimension:
        raise ValueError("stored embedding dimension does not match vector data")
    return list(vector)


def build_embeddings(
    database: Database,
    course: str,
    encoder: Encoder,
) -> int:
    rows = database.connection.execute(
        """
        SELECT slides.id, slides.title, slides.body_text, slides.speaker_notes,
               slides.visual_description, slides.ocr_text
        FROM slides
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE courses.name = ?
        ORDER BY slides.id
        """,
        (course,),
    ).fetchall()
    if not rows:
        return 0

    vectors = list(encoder.encode([_searchable_text(row) for row in rows]))
    if len(vectors) != len(rows):
        raise ValueError("encoder returned the wrong number of vectors")

    with database.connection:
        for row, values in zip(rows, vectors, strict=True):
            dimension, blob = _encode_blob(values)
            database.connection.execute(
                """
                INSERT INTO slide_embeddings(slide_id, model_name, dimension, vector)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(slide_id, model_name) DO UPDATE SET
                    dimension = excluded.dimension,
                    vector = excluded.vector
                """,
                (row["id"], encoder.model_name, dimension, blob),
            )
    return len(rows)


def semantic_ranking(
    database: Database,
    query: str,
    encoder: Encoder,
    *,
    course: str | None = None,
    source_file: str | None = None,
    ordinal: int | None = None,
) -> list[int]:
    encoded = list(encoder.encode([query]))
    if len(encoded) != 1:
        raise ValueError("encoder must return one vector for one query")
    query_vector = _normalize(encoded[0])

    parameters: list[object] = [encoder.model_name]
    filter_clauses: list[str] = []
    if course is not None:
        filter_clauses.append("courses.name = ?")
        parameters.append(course)
    if source_file is not None:
        filter_clauses.append("source_files.relative_path = ?")
        parameters.append(source_file)
    if ordinal is not None:
        filter_clauses.append("slides.ordinal = ?")
        parameters.append(ordinal)
    filter_sql = "".join(f" AND {clause}" for clause in filter_clauses)
    rows = database.connection.execute(
        f"""
        SELECT slide_embeddings.slide_id, slide_embeddings.dimension,
               slide_embeddings.vector
        FROM slide_embeddings
        JOIN slides ON slides.id = slide_embeddings.slide_id
        JOIN source_files ON source_files.id = slides.source_file_id
        JOIN courses ON courses.id = source_files.course_id
        WHERE slide_embeddings.model_name = ?
        {filter_sql}
        """,
        parameters,
    ).fetchall()

    scored: list[tuple[float, int]] = []
    for row in rows:
        stored = _decode_blob(row["vector"], row["dimension"])
        if len(stored) != len(query_vector):
            continue
        score = sum(left * right for left, right in zip(query_vector, stored))
        scored.append((score, int(row["slide_id"])))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [slide_id for _, slide_id in scored]


__all__ = ["Encoder", "build_embeddings", "semantic_ranking"]
