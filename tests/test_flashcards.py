import json
from pathlib import Path

import pytest

from classcorpus.flashcards import Flashcard, export_flashcards, load_flashcards


@pytest.fixture
def cards() -> list[Flashcard]:
    return [
        Flashcard(
            front="What does memoization avoid?",
            back="Repeated evaluation\nof overlapping subproblems.",
            citation="[Algorithms, Lecture08.pptx, Slide 27]",
            tags=("dynamic programming", "lecture-08"),
        ),
        Flashcard(
            front="Can Bellman-Ford use negative edges?",
            back="Yes.",
            citation="[Algorithms, handout.pdf, Page 3]",
        ),
    ]


@pytest.mark.parametrize("format_name", ["json", "csv", "tsv"])
def test_flashcard_formats_round_trip_losslessly(
    tmp_path: Path,
    cards: list[Flashcard],
    format_name: str,
):
    path = tmp_path / f"cards.{format_name}"

    export_flashcards(cards, path)

    assert load_flashcards(path) == cards


def test_json_import_accepts_agent_cards_array(tmp_path: Path):
    path = tmp_path / "cards.json"
    path.write_text(
        json.dumps(
            [
                {
                    "front": "Question",
                    "back": "Answer",
                    "citation": "[Course, lecture.md, Page 1]",
                    "tags": ["week-1"],
                }
            ]
        ),
        encoding="utf-8",
    )

    cards = load_flashcards(path)

    assert cards == [
        Flashcard(
            "Question",
            "Answer",
            "[Course, lecture.md, Page 1]",
            ("week-1",),
        )
    ]


def test_delimited_import_requires_front_and_back_headers(tmp_path: Path):
    path = tmp_path / "cards.csv"
    path.write_text("question,answer\nQ,A\n", encoding="utf-8")

    with pytest.raises(ValueError, match="header is missing"):
        load_flashcards(path)


def test_export_refuses_implicit_overwrite(
    tmp_path: Path,
    cards: list[Flashcard],
):
    path = tmp_path / "cards.json"
    path.write_text("original", encoding="utf-8")

    with pytest.raises(FileExistsError, match="--overwrite"):
        export_flashcards(cards, path)

    assert path.read_text(encoding="utf-8") == "original"
    export_flashcards(cards, path, overwrite=True)
    assert load_flashcards(path) == cards


@pytest.mark.parametrize(
    "payload",
    [
        [{"front": "", "back": "Answer"}],
        [{"front": "Question", "back": ""}],
        [{"front": "Question", "back": "Answer", "tags": [1]}],
    ],
)
def test_import_rejects_invalid_cards(tmp_path: Path, payload):
    path = tmp_path / "cards.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError):
        load_flashcards(path)
