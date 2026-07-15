import json
from pathlib import Path
import re

import pytest

from classcorpus.flashcard_html import (
    render_flashcards_html,
    write_flashcards_html,
)
from classcorpus.flashcards import Flashcard


@pytest.fixture
def cards() -> list[Flashcard]:
    return [
        Flashcard(
            front="What is memoization?",
            back="Caching repeated subproblems.",
            citation="[Algorithms, Lecture08.pptx, Slide 2]",
            tags=("dynamic-programming", "lecture-08"),
        ),
        Flashcard(
            front="Can it preserve\nmultiple lines?",
            back="Yes.",
            tags=("lecture-08",),
        ),
    ]


def embedded_cards(document: str) -> list[dict]:
    match = re.search(
        r'<script id="flashcard-data" type="application/json">(.*?)</script>',
        document,
        flags=re.DOTALL,
    )
    assert match is not None
    return json.loads(match.group(1))


def test_rendered_deck_is_self_contained_and_preserves_cards(
    cards: list[Flashcard],
):
    document = render_flashcards_html(cards, title="Algorithms Review")

    assert document.startswith("<!doctype html>")
    assert "<title>Algorithms Review</title>" in document
    assert embedded_cards(document) == [
        {
            "front": card.front,
            "back": card.back,
            "citation": card.citation,
            "tags": list(card.tags),
        }
        for card in cards
    ]
    assert "https://" not in document
    assert "http://" not in document
    assert "fetch(" not in document
    assert "XMLHttpRequest" not in document
    assert "WebSocket" not in document


def test_rendered_deck_escapes_html_and_script_terminators():
    hostile = Flashcard(
        front='</script><script>alert("front")</script>',
        back="<img src=x onerror=alert('back')>",
        citation="A & B",
        tags=("<b>tag</b>",),
    )

    document = render_flashcards_html(
        [hostile],
        title="<img src=x onerror=alert('title')>",
    )

    assert "<title>&lt;img src=x onerror=alert(&#x27;title&#x27;)&gt;</title>" in (
        document
    )
    assert '</script><script>alert("front")</script>' not in document
    assert "<img src=x onerror=alert('back')>" not in document
    assert embedded_cards(document)[0] == {
        "front": hostile.front,
        "back": hostile.back,
        "citation": hostile.citation,
        "tags": list(hostile.tags),
    }


@pytest.mark.parametrize("title", ["", "   "])
def test_rendered_deck_rejects_blank_titles(
    cards: list[Flashcard],
    title: str,
):
    with pytest.raises(ValueError, match="title must not be blank"):
        render_flashcards_html(cards, title=title)


def test_rendered_deck_rejects_empty_card_list():
    with pytest.raises(ValueError, match="at least one card"):
        render_flashcards_html([])


def test_html_export_refuses_implicit_overwrite(
    tmp_path: Path,
    cards: list[Flashcard],
):
    path = tmp_path / "cards.html"
    path.write_text("original", encoding="utf-8")

    with pytest.raises(FileExistsError, match="--overwrite"):
        write_flashcards_html(cards, path)

    assert path.read_text(encoding="utf-8") == "original"
    write_flashcards_html(cards, path, overwrite=True)
    assert embedded_cards(path.read_text(encoding="utf-8"))[0]["front"] == (
        cards[0].front
    )
