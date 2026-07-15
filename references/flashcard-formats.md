# Flashcard Interchange

ClassCorpus converts cited flashcards between JSON, CSV, and TSV without
creating a flashcard database or depending on a specific study application.

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
- CSV and TSV require a header row with `front` and `back`. Optional columns
  are `citation` and `tags`.
- CSV/TSV tags are encoded as a JSON array inside the tags cell. Import also
  accepts semicolon-separated tags for manually authored files.
- UTF-8 with an optional byte-order mark is accepted on delimited import.
- Embedded commas, tabs, quotes, and newlines use standard CSV quoting.

The delimited output can be imported into spreadsheet tools and flashcard
applications that accept mapped text fields. Map the four named columns rather
than assuming an application-specific deck schema.

## Conversion

```text
python scripts/convert_flashcards.py INPUT OUTPUT \
  [--input-format json|csv|tsv] \
  [--output-format json|csv|tsv] [--overwrite] --json
```

Formats are inferred from file extensions when flags are omitted. Export is
atomic and refuses an existing destination unless `--overwrite` is explicit.
Conversion never modifies the input file.

