#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from _common import argument_parser, emit, fail
from classcorpus.flashcard_html import DEFAULT_TITLE, write_flashcards_html
from classcorpus.flashcards import load_flashcards


def main() -> int:
    parser = argument_parser(
        description="Render cited flashcards as a self-contained interactive deck."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", default=DEFAULT_TITLE)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        cards = load_flashcards(args.input)
        write_flashcards_html(
            cards,
            args.output,
            title=args.title,
            overwrite=args.overwrite,
        )
        emit(
            {
                "ok": True,
                "rendered": len(cards),
                "input": str(args.input.resolve()),
                "output": str(args.output.resolve()),
                "title": args.title.strip(),
            },
            json_mode=args.json_mode,
        )
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())
