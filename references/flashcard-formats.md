# Flashcard Outputs

ClassCorpus keeps cited JSON as the portable source, renders a self-contained
interactive HTML deck by default, and converts to CSV or TSV when requested.
It does not create a flashcard database or depend on a specific study
application.

## Normalized Card

```json
{
  "front": "What problem does memoization avoid?",
  "back": "Repeated evaluation of overlapping subproblems.",
  "citation": "[Algorithms, Lecture08.pptx, Slide 27]",
  "tags": ["dynamic-programming", "lecture-08"]
}
```

`front` and `back` are required nonblank strings. `citation` is an optional
string. `tags` is an optional array of nonblank strings.

## Formats

- JSON accepts either a top-level card array or `{"cards": [...]}`.
- HTML is generated from JSON with `render_flashcards.py`. It embeds all data,
  styles, and behavior locally; no network access or external assets are used.
- CSV and TSV require a header row with `front` and `back`. Optional columns
  are `citation` and `tags`.
- CSV/TSV tags are encoded as a JSON array inside the tags cell. Import also
  accepts semicolon-separated tags for manually authored files.
- UTF-8 with an optional byte-order mark is accepted on delimited import.
- Embedded commas, tabs, quotes, and newlines use standard CSV quoting.

The delimited output can be imported into spreadsheet tools and flashcard
applications that accept mapped text fields. Map the four named columns rather
than assuming an application-specific deck schema.

## Interactive Deck

```text
python scripts/render_flashcards.py INPUT.json OUTPUT.html \
  [--title TITLE] [--overwrite] --json
```

The deck provides reveal, previous/next, shuffle, exact-tag filtering, and
session-only known/review tracking. Card content is inserted as text, and
embedded JSON is escaped to prevent HTML or script injection. Rendering is
atomic and refuses an existing destination unless `--overwrite` is explicit.

## Conversion

```text
python scripts/convert_flashcards.py INPUT OUTPUT \
  [--input-format json|csv|tsv] \
  [--output-format json|csv|tsv] [--overwrite] --json
```

Formats are inferred from file extensions when flags are omitted. Export is
atomic and refuses an existing destination unless `--overwrite` is explicit.
Conversion never modifies the input file.
