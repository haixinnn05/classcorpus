#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from _common import argument_parser, emit, fail
from classcorpus.flashcards import export_flashcards, load_flashcards


def main() -> int:
    parser = argument_parser(
        description="Convert cited flashcards between JSON, CSV, and TSV."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--input-format",
        choices=("json", "csv", "tsv"),
    )
    parser.add_argument(
        "--output-format",
        choices=("json", "csv", "tsv"),
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_mode")
    args = parser.parse_args()
    try:
        cards = load_flashcards(args.input, format_name=args.input_format)
        export_flashcards(
            cards,
            args.output,
            format_name=args.output_format,
            overwrite=args.overwrite,
        )
        emit(
            {
                "ok": True,
                "converted": len(cards),
                "input": str(args.input.resolve()),
                "output": str(args.output.resolve()),
            },
            json_mode=args.json_mode,
        )
        return 0
    except Exception as error:
        return fail(error, json_mode=args.json_mode)


if __name__ == "__main__":
    raise SystemExit(main())

