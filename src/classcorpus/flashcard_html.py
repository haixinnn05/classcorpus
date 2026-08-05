from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import asdict
from html import escape
from pathlib import Path
from typing import Sequence

from classcorpus.flashcards import Flashcard
from classcorpus.study_progress import CardIdentity, identify_card_content

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
    .rating,
    .confidence {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .toolbar {
      flex-wrap: wrap;
      justify-content: flex-end;
    }

    .toolbar .secondary-action {
      min-height: 38px;
      padding: 6px 10px;
      font-size: 0.8125rem;
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

    .confidence {
      justify-content: center;
    }

    .confidence label {
      width: min(100%, 300px);
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
        <label for="queue-filter">
          Queue
          <select id="queue-filter">
            <option value="due">Due and new</option>
            <option value="all">All cards</option>
          </select>
        </label>
        <button id="shuffle" type="button">Shuffle</button>
        <button id="export-progress" class="secondary-action" type="button">Export progress</button>
        <button id="import-progress" class="secondary-action" type="button">Import progress</button>
        <input id="progress-file" type="file" accept="application/json,.json" hidden>
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
      <div class="confidence">
        <label for="confidence">
          Confidence before reveal
          <select id="confidence">
            <option value="">Choose 1–5</option>
            <option value="1">1 — guessing</option>
            <option value="2">2 — unsure</option>
            <option value="3">3 — somewhat sure</option>
            <option value="4">4 — confident</option>
            <option value="5">5 — very confident</option>
          </select>
        </label>
      </div>
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
        <button id="again" class="review" type="button">Again</button>
        <button id="hard" type="button">Hard</button>
        <button id="good" class="known" type="button">Good</button>
        <button id="easy" class="known" type="button">Easy</button>
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
      const cards = source;
      const filter = document.getElementById("tag-filter");
      const queueFilter = document.getElementById("queue-filter");
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
      const confidence = document.getElementById("confidence");
      const previous = document.getElementById("previous");
      const next = document.getElementById("next");
      const storageKey = `classcorpus:review:v1:${cards.map((card) => card.id).sort().join(":")}`;
      let stored = loadStoredProgress();

      let deck = [];
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

      function loadStoredProgress() {
        try {
          const parsed = JSON.parse(localStorage.getItem(storageKey) || "null");
          if (parsed && parsed.version === 1 && parsed.reviews && Array.isArray(parsed.events)) {
            return parsed;
          }
        } catch (_) {
          // A corrupt local entry should not prevent the deck from opening.
        }
        return { version: 1, reviews: {}, events: [] };
      }

      function persistProgress() {
        try {
          localStorage.setItem(storageKey, JSON.stringify(stored));
          return true;
        } catch (_) {
          progress.textContent = "Browser storage is unavailable; export progress before closing.";
          return false;
        }
      }

      function cardStatus(card, now = Date.now()) {
        const state = stored.reviews[card.id];
        if (!state) return "new";
        return Date.parse(state.due_at) <= now ? "due" : "future";
      }

      function rebuildDeck() {
        deck = cards.filter((card) => {
          const topicMatches = !filter.value || card.tags.includes(filter.value);
          const queueMatches = queueFilter.value === "all" || cardStatus(card) !== "future";
          return topicMatches && queueMatches;
        });
        current = 0;
        revealed = false;
        render();
      }

      function updateProgress() {
        const statuses = cards.map((card) => cardStatus(card));
        const due = statuses.filter((value) => value === "due").length;
        const fresh = statuses.filter((value) => value === "new").length;
        const scheduled = statuses.filter((value) => value === "future").length;
        progress.textContent = `${due} due · ${fresh} new · ${scheduled} scheduled`;
      }

      function render() {
        if (!deck.length) {
          position.textContent = "Queue complete";
          deckCount.textContent = `${cards.length} ${cards.length === 1 ? "card" : "cards"}`;
          question.textContent = "No cards are due right now.";
          answer.hidden = true;
          rating.hidden = true;
          reveal.hidden = true;
          confidence.disabled = true;
          previous.disabled = true;
          next.disabled = true;
          tags.replaceChildren();
          updateProgress();
          return;
        }
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
        confidence.disabled = revealed;
        if (!revealed) confidence.value = "";
        reveal.disabled = !confidence.value;
        previous.disabled = false;
        next.disabled = false;
        reveal.setAttribute("aria-expanded", String(revealed));
        updateProgress();
      }

      function move(direction) {
        current = (current + direction + deck.length) % deck.length;
        revealed = false;
        render();
      }

      function showAnswer() {
        if (revealed || !confidence.value || !deck.length) return;
        revealed = true;
        render();
      }

      function schedule(value, state) {
        let repetitions = state ? state.repetitions : 0;
        let lapses = state ? state.lapses : 0;
        let interval = state ? state.interval_days : 0;
        let ease = state ? state.ease : 2.5;
        if (value === "again") {
          repetitions = 0;
          lapses += 1;
          interval = 10 / 1440;
          ease = Math.max(1.3, ease - 0.2);
        } else if (value === "hard") {
          repetitions += 1;
          interval = Math.max(1, interval * 1.2);
          ease = Math.max(1.3, ease - 0.15);
        } else if (value === "good") {
          interval = repetitions === 0 ? 1 : repetitions === 1 ? 6 : Math.max(interval + 1, Math.round(interval * ease * 10) / 10);
          repetitions += 1;
        } else {
          interval = repetitions === 0 ? 4 : repetitions === 1 ? 7 : Math.max(interval + 2, Math.round(interval * (ease + 0.3) * 10) / 10);
          repetitions += 1;
          ease += 0.15;
        }
        return { repetitions, lapses, interval, ease };
      }

      function rate(value) {
        if (!revealed || !deck.length) return;
        const card = deck[current];
        const reviewedAt = new Date();
        const previousState = stored.reviews[card.id] || null;
        const result = schedule(value, previousState);
        const dueAt = new Date(reviewedAt.getTime() + result.interval * 86400000);
        const createdAt = previousState ? previousState.created_at : reviewedAt.toISOString();
        const review = {
          card_id: card.id,
          card_key: card.card_key,
          source_sha256: card.source_sha256,
          citation: card.citation,
          repetitions: result.repetitions,
          lapses: result.lapses,
          interval_days: result.interval,
          ease: result.ease,
          due_at: dueAt.toISOString(),
          last_reviewed_at: reviewedAt.toISOString(),
          created_at: createdAt,
          updated_at: reviewedAt.toISOString()
        };
        stored.reviews[card.id] = review;
        stored.events.push({
          card_id: card.id,
          rating: value,
          confidence: Number(confidence.value),
          reviewed_at: reviewedAt.toISOString(),
          previous_due_at: previousState ? previousState.due_at : null,
          new_due_at: dueAt.toISOString()
        });
        persistProgress();
        if (queueFilter.value === "due") rebuildDeck();
        else move(1);
      }

      filter.addEventListener("change", rebuildDeck);
      queueFilter.addEventListener("change", rebuildDeck);
      confidence.addEventListener("change", () => {
        reveal.disabled = !confidence.value;
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
      previous.addEventListener("click", () => move(-1));
      next.addEventListener("click", () => move(1));
      document.getElementById("again").addEventListener("click", () => rate("again"));
      document.getElementById("hard").addEventListener("click", () => rate("hard"));
      document.getElementById("good").addEventListener("click", () => rate("good"));
      document.getElementById("easy").addEventListener("click", () => rate("easy"));
      reveal.addEventListener("click", showAnswer);

      document.getElementById("export-progress").addEventListener("click", () => {
        const payload = {
          format: "classcorpus-study-progress",
          version: 1,
          exported_at: new Date().toISOString(),
          reviews: Object.values(stored.reviews),
          events: stored.events
        };
        const blob = new Blob([JSON.stringify(payload, null, 2) + "\\n"], { type: "application/json" });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "classcorpus-progress.json";
        link.click();
        URL.revokeObjectURL(link.href);
      });

      const progressFile = document.getElementById("progress-file");
      document.getElementById("import-progress").addEventListener("click", () => progressFile.click());
      progressFile.addEventListener("change", async () => {
        const file = progressFile.files[0];
        if (!file) return;
        try {
          const imported = JSON.parse(await file.text());
          if (imported.format !== "classcorpus-study-progress" || imported.version !== 1 || !Array.isArray(imported.reviews) || !Array.isArray(imported.events)) {
            throw new Error("Unsupported progress file");
          }
          imported.reviews.forEach((review) => {
            const existing = stored.reviews[review.card_id];
            if (!existing || review.updated_at >= existing.updated_at) stored.reviews[review.card_id] = review;
          });
          const eventKeys = new Set(stored.events.map((event) => `${event.card_id}|${event.reviewed_at}|${event.rating}`));
          imported.events.forEach((event) => {
            const key = `${event.card_id}|${event.reviewed_at}|${event.rating}`;
            if (!eventKeys.has(key)) {
              stored.events.push(event);
              eventKeys.add(key);
            }
          });
          persistProgress();
          rebuildDeck();
        } catch (error) {
          progress.textContent = `Import failed: ${error.message}`;
        } finally {
          progressFile.value = "";
        }
      });

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

      rebuildDeck();
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
    identities: Sequence[CardIdentity] | None = None,
) -> str:
    values = list(cards)
    if not values:
        raise ValueError("interactive flashcard deck must contain at least one card")
    clean_title = title.strip()
    if not clean_title:
        raise ValueError("flashcard deck title must not be blank")
    identity_values = (
        list(identities)
        if identities is not None
        else [identify_card_content(card) for card in values]
    )
    if len(identity_values) != len(values):
        raise ValueError("flashcard identities must match the card count")
    payload = json.dumps(
        [
            {
                **asdict(card),
                "id": identity.card_id,
                "card_key": identity.card_key,
                "source_sha256": identity.source_sha256,
            }
            for card, identity in zip(values, identity_values, strict=True)
        ],
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
    identities: Sequence[CardIdentity] | None = None,
    overwrite: bool = False,
) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"output already exists: {path}; pass --overwrite to replace it"
        )
    document = render_flashcards_html(cards, title=title, identities=identities)
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
