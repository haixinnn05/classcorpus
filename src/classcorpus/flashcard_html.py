from __future__ import annotations

from dataclasses import asdict
from html import escape
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Sequence

from classcorpus.flashcards import Flashcard

DEFAULT_TITLE = "Study Flashcards"

_DOCUMENT = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <style>
    :root {
      color-scheme: light;
      --page: #f4f5f2;
      --surface: #ffffff;
      --surface-soft: #edf4f2;
      --ink: #17212b;
      --muted: #5b6872;
      --line: #cbd7dd;
      --primary: #147d92;
      --primary-hover: #0f687a;
      --primary-text: #ffffff;
      --focus: #d99a20;
      --known: #237a57;
      --review: #9b6415;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
    }

    * {
      box-sizing: border-box;
    }

    body {
      min-width: 320px;
      margin: 0;
      background: var(--page);
      color: var(--ink);
    }

    button,
    select {
      font: inherit;
    }

    button:focus-visible,
    select:focus-visible {
      outline: 3px solid var(--focus);
      outline-offset: 2px;
    }

    .shell {
      width: min(100% - 32px, 880px);
      margin: 0 auto;
      padding: 32px 0 48px;
    }

    header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 20px;
      margin-bottom: 20px;
    }

    h1,
    h2,
    p {
      margin-top: 0;
    }

    h1 {
      margin-bottom: 4px;
      font-size: 1.75rem;
      font-weight: 700;
    }

    .deck-count,
    .status-detail,
    .citation {
      color: var(--muted);
    }

    .deck-count,
    .status-detail {
      margin-bottom: 0;
      font-size: 0.875rem;
    }

    .toolbar,
    .status,
    .navigation,
    .rating {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .toolbar {
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    label {
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
    }

    select,
    button {
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      color: var(--ink);
    }

    select {
      max-width: 280px;
      padding: 8px 34px 8px 11px;
    }

    button {
      padding: 8px 14px;
      cursor: pointer;
      font-weight: 650;
    }

    button:hover {
      border-color: var(--primary);
    }

    .primary {
      border-color: var(--primary);
      background: var(--primary);
      color: var(--primary-text);
    }

    .primary:hover {
      border-color: var(--primary-hover);
      background: var(--primary-hover);
    }

    .status {
      justify-content: space-between;
      min-height: 28px;
      margin-bottom: 10px;
    }

    .status strong {
      font-size: 0.9375rem;
    }

    .card {
      display: grid;
      align-content: center;
      min-height: 340px;
      padding: 36px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      box-shadow: 0 8px 24px rgb(23 33 43 / 8%);
    }

    .tags {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      min-height: 25px;
      margin-bottom: 22px;
    }

    .tag {
      padding: 4px 8px;
      border-radius: 999px;
      background: var(--surface-soft);
      color: var(--primary-hover);
      font-size: 0.75rem;
      font-weight: 700;
    }

    h2 {
      max-width: 34ch;
      margin-bottom: 0;
      overflow-wrap: anywhere;
      font-size: 1.5rem;
      line-height: 1.35;
    }

    .answer {
      margin-top: 24px;
      padding-top: 24px;
      border-top: 1px solid var(--line);
    }

    .answer-text {
      margin-bottom: 14px;
      overflow-wrap: anywhere;
      font-size: 1.125rem;
      line-height: 1.6;
      white-space: pre-wrap;
    }

    .citation {
      margin-bottom: 0;
      overflow-wrap: anywhere;
      font-size: 0.8125rem;
      line-height: 1.5;
    }

    [hidden] {
      display: none !important;
    }

    .actions {
      display: grid;
      gap: 10px;
      margin-top: 16px;
    }

    .navigation,
    .rating {
      justify-content: center;
    }

    .known {
      color: var(--known);
    }

    .review {
      color: var(--review);
    }

    .keyboard-help {
      margin: 18px 0 0;
      color: var(--muted);
      font-size: 0.75rem;
      text-align: center;
    }

    kbd {
      padding: 1px 5px;
      border: 1px solid var(--line);
      border-bottom-width: 2px;
      border-radius: 4px;
      background: var(--surface);
      font: inherit;
    }

    @media (max-width: 620px) {
      .shell {
        width: min(100% - 24px, 880px);
        padding-top: 20px;
      }

      header {
        align-items: stretch;
        flex-direction: column;
      }

      .toolbar {
        justify-content: flex-start;
      }

      label,
      select {
        width: 100%;
        max-width: none;
      }

      .status {
        align-items: flex-start;
        flex-direction: column;
        gap: 3px;
      }

      .card {
        min-height: 320px;
        padding: 24px 20px;
      }

      h1 {
        font-size: 1.5rem;
      }

      h2 {
        font-size: 1.25rem;
      }

      .navigation,
      .rating {
        display: grid;
        grid-template-columns: 1fr 1fr;
      }

      .navigation .primary {
        grid-column: 1 / -1;
        grid-row: 1;
      }

      .rating button {
        width: 100%;
      }

      .keyboard-help {
        display: none;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <h1>__TITLE__</h1>
        <p class="deck-count" id="deck-count"></p>
      </div>
      <div class="toolbar">
        <label for="tag-filter">
          Topic
          <select id="tag-filter">
            <option value="">All cards</option>
          </select>
        </label>
        <button id="shuffle" type="button">Shuffle</button>
      </div>
    </header>

    <div class="status" aria-live="polite">
      <strong id="position"></strong>
      <p class="status-detail" id="progress"></p>
    </div>

    <article class="card" aria-labelledby="question">
      <div class="tags" id="tags" aria-label="Card topics"></div>
      <h2 id="question"></h2>
      <div class="answer" id="answer" hidden>
        <p class="answer-text" id="answer-text"></p>
        <p class="citation" id="citation"></p>
      </div>
    </article>

    <div class="actions">
      <div class="navigation">
        <button id="previous" type="button">Previous</button>
        <button
          id="reveal"
          class="primary"
          type="button"
          aria-controls="answer"
          aria-expanded="false"
        >Reveal answer</button>
        <button id="next" type="button">Next</button>
      </div>
      <div class="rating" id="rating" hidden>
        <button id="review" class="review" type="button">Review again</button>
        <button id="known" class="known" type="button">Know it</button>
      </div>
    </div>

    <p class="keyboard-help">
      <kbd>Space</kbd> reveal
      &nbsp; <kbd>←</kbd> previous
      &nbsp; <kbd>→</kbd> next
    </p>
    <noscript>This interactive deck requires JavaScript. Use the accompanying JSON deck as a text fallback.</noscript>
  </main>

  <script id="flashcard-data" type="application/json">__CARD_DATA__</script>
  <script>
    (() => {
      "use strict";

      const source = JSON.parse(
        document.getElementById("flashcard-data").textContent
      );
      const cards = source.map((card, index) => ({ ...card, id: index }));
      const filter = document.getElementById("tag-filter");
      const position = document.getElementById("position");
      const progress = document.getElementById("progress");
      const deckCount = document.getElementById("deck-count");
      const tags = document.getElementById("tags");
      const question = document.getElementById("question");
      const answer = document.getElementById("answer");
      const answerText = document.getElementById("answer-text");
      const citation = document.getElementById("citation");
      const reveal = document.getElementById("reveal");
      const rating = document.getElementById("rating");
      const ratings = new Map();

      let deck = cards.slice();
      let current = 0;
      let revealed = false;

      const allTags = [...new Set(cards.flatMap((card) => card.tags))]
        .sort((left, right) => left.localeCompare(right));
      allTags.forEach((tag) => {
        const option = document.createElement("option");
        option.value = tag;
        option.textContent = tag;
        filter.append(option);
      });

      function updateProgress() {
        const values = [...ratings.values()];
        const known = values.filter((value) => value === "known").length;
        const review = values.filter((value) => value === "review").length;
        progress.textContent = `${known} known · ${review} review`;
      }

      function render() {
        const card = deck[current];
        position.textContent = `Card ${current + 1} of ${deck.length}`;
        deckCount.textContent = `${cards.length} ${cards.length === 1 ? "card" : "cards"}`;
        question.textContent = card.front;
        answerText.textContent = card.back;
        citation.textContent = card.citation;
        citation.hidden = !card.citation;
        tags.replaceChildren();
        card.tags.forEach((value) => {
          const tag = document.createElement("span");
          tag.className = "tag";
          tag.textContent = value;
          tags.append(tag);
        });
        answer.hidden = !revealed;
        rating.hidden = !revealed;
        reveal.hidden = revealed;
        reveal.setAttribute("aria-expanded", String(revealed));
        updateProgress();
      }

      function move(direction) {
        current = (current + direction + deck.length) % deck.length;
        revealed = false;
        render();
      }

      function showAnswer() {
        if (revealed) return;
        revealed = true;
        render();
      }

      function rate(value) {
        ratings.set(deck[current].id, value);
        move(1);
      }

      filter.addEventListener("change", () => {
        deck = filter.value
          ? cards.filter((card) => card.tags.includes(filter.value))
          : cards.slice();
        current = 0;
        revealed = false;
        render();
      });

      document.getElementById("shuffle").addEventListener("click", () => {
        for (let index = deck.length - 1; index > 0; index -= 1) {
          const swapIndex = Math.floor(Math.random() * (index + 1));
          [deck[index], deck[swapIndex]] = [deck[swapIndex], deck[index]];
        }
        current = 0;
        revealed = false;
        render();
      });
      document.getElementById("previous").addEventListener("click", () => move(-1));
      document.getElementById("next").addEventListener("click", () => move(1));
      document.getElementById("review").addEventListener("click", () => rate("review"));
      document.getElementById("known").addEventListener("click", () => rate("known"));
      reveal.addEventListener("click", showAnswer);

      document.addEventListener("keydown", (event) => {
        if (event.target.matches("button, select")) return;
        if (event.key === " ") {
          event.preventDefault();
          showAnswer();
        } else if (event.key === "ArrowLeft") {
          move(-1);
        } else if (event.key === "ArrowRight") {
          move(1);
        }
      });

      render();
    })();
  </script>
</body>
</html>
"""
_PLACEHOLDER_PATTERN = re.compile(r"__TITLE__|__CARD_DATA__")


def render_flashcards_html(
    cards: Sequence[Flashcard],
    *,
    title: str = DEFAULT_TITLE,
) -> str:
    values = list(cards)
    if not values:
        raise ValueError("interactive flashcard deck must contain at least one card")
    clean_title = title.strip()
    if not clean_title:
        raise ValueError("flashcard deck title must not be blank")
    payload = json.dumps(
        [asdict(card) for card in values],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    safe_payload = (
        payload.replace("&", r"\u0026")
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
        .replace("\u2028", r"\u2028")
        .replace("\u2029", r"\u2029")
    )
    replacements = {
        "__TITLE__": escape(clean_title),
        "__CARD_DATA__": safe_payload,
    }
    return _PLACEHOLDER_PATTERN.sub(
        lambda match: replacements[match.group(0)],
        _DOCUMENT,
    )


def write_flashcards_html(
    cards: Sequence[Flashcard],
    path: Path,
    *,
    title: str = DEFAULT_TITLE,
    overwrite: bool = False,
) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"output already exists: {path}; pass --overwrite to replace it"
        )
    document = render_flashcards_html(cards, title=title)
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
            stream.write(document)
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


__all__ = [
    "DEFAULT_TITLE",
    "render_flashcards_html",
    "write_flashcards_html",
]
