from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Literal, Sequence

FlashcardFormat = Literal["json", "csv", "tsv"]
FIELDS = ("front", "back", "citation", "tags")


@dataclass(frozen=True, slots=True)
class Flashcard:
    front: str
    back: str
    citation: str = ""
    tags: tuple[str, ...] = ()


def load_flashcards(
    path: Path,
    *,
    format_name: FlashcardFormat | None = None,
) -> list[Flashcard]:
    selected = format_name or _format_from_path(path)
    if selected == "json":
        return _load_json(path)
    if selected in {"csv", "tsv"}:
        return _load_delimited(path, delimiter="," if selected == "csv" else "\t")
    raise ValueError(f"unsupported flashcard format: {selected}")


def export_flashcards(
    cards: Sequence[Flashcard],
    path: Path,
    *,
    format_name: FlashcardFormat | None = None,
    overwrite: bool = False,
) -> None:
    selected = format_name or _format_from_path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"output already exists: {path}; pass --overwrite to replace it"
        )
    validated = [_validate_card(card) for card in cards]
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            if selected == "json":
                json.dump(
                    {"cards": [asdict(card) for card in validated]},
                    stream,
                    ensure_ascii=False,
                    indent=2,
                )
                stream.write("\n")
            elif selected in {"csv", "tsv"}:
                _write_delimited(
                    stream,
                    validated,
                    delimiter="," if selected == "csv" else "\t",
                )
            else:
                raise ValueError(f"unsupported flashcard format: {selected}")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _load_json(path: Path) -> list[Flashcard]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("cards") if isinstance(payload, dict) else payload
    if not isinstance(values, list):
        raise ValueError("JSON flashcards must be an array or a cards array")
    return [_card_from_mapping(value, index + 1) for index, value in enumerate(values)]


def _load_delimited(path: Path, *, delimiter: str) -> list[Flashcard]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError("flashcard file must include a header row")
        names = {name.casefold(): name for name in reader.fieldnames}
        missing = {"front", "back"} - set(names)
        if missing:
            raise ValueError(
                "flashcard header is missing: " + ", ".join(sorted(missing))
            )
        cards: list[Flashcard] = []
        for row_number, row in enumerate(reader, start=2):
            normalized = {
                field: row.get(names[field], "") if field in names else ""
                for field in FIELDS
            }
            cards.append(_card_from_mapping(normalized, row_number))
        return cards


def _write_delimited(stream, cards: Sequence[Flashcard], *, delimiter: str) -> None:
    writer = csv.DictWriter(
        stream,
        fieldnames=FIELDS,
        delimiter=delimiter,
        lineterminator="\n",
    )
    writer.writeheader()
    for card in cards:
        writer.writerow(
            {
                "front": card.front,
                "back": card.back,
                "citation": card.citation,
                "tags": json.dumps(
                    card.tags,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            }
        )


def _card_from_mapping(value, position: int) -> Flashcard:
    if not isinstance(value, dict):
        raise ValueError(f"flashcard {position} must be an object")
    front = value.get("front")
    back = value.get("back")
    citation = value.get("citation", "")
    tags = value.get("tags", ())
    if isinstance(tags, str):
        stripped = tags.strip()
        if stripped.startswith("["):
            try:
                tags = json.loads(stripped)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"flashcard {position} tags contain invalid JSON"
                ) from error
        elif stripped:
            tags = [tag.strip() for tag in stripped.split(";") if tag.strip()]
        else:
            tags = []
    if not isinstance(tags, (list, tuple)) or not all(
        isinstance(tag, str) and tag.strip() for tag in tags
    ):
        raise ValueError(f"flashcard {position} tags must be nonblank strings")
    if not isinstance(citation, str):
        raise ValueError(f"flashcard {position} citation must be a string")
    return _validate_card(
        Flashcard(
            front=front if isinstance(front, str) else "",
            back=back if isinstance(back, str) else "",
            citation=citation,
            tags=tuple(tag.strip() for tag in tags),
        ),
        position=position,
    )


def _validate_card(card: Flashcard, *, position: int | None = None) -> Flashcard:
    label = f"flashcard {position}" if position is not None else "flashcard"
    if not isinstance(card, Flashcard):
        raise ValueError(f"{label} must be a Flashcard")
    front = card.front.strip()
    back = card.back.strip()
    if not front:
        raise ValueError(f"{label} front must not be blank")
    if not back:
        raise ValueError(f"{label} back must not be blank")
    if not isinstance(card.citation, str):
        raise ValueError(f"{label} citation must be a string")
    if not all(isinstance(tag, str) and tag.strip() for tag in card.tags):
        raise ValueError(f"{label} tags must be nonblank strings")
    return Flashcard(
        front=front,
        back=back,
        citation=card.citation.strip(),
        tags=tuple(tag.strip() for tag in card.tags),
    )


def _format_from_path(path: Path) -> FlashcardFormat:
    suffix = path.suffix.casefold().lstrip(".")
    if suffix not in {"json", "csv", "tsv"}:
        raise ValueError(
            "flashcard format must be json, csv, or tsv "
            "(or use a matching file extension)"
        )
    return suffix  # type: ignore[return-value]


__all__ = [
    "Flashcard",
    "FlashcardFormat",
    "export_flashcards",
    "load_flashcards",
]
