# Example Workflow

The test suite creates deterministic PDF and PPTX fixtures, so contributors can
exercise the complete workflow without committing copyrighted lecture decks.

```bash
.venv/bin/python -m pytest -q tests/test_scripts.py
```

For a personal lecture folder:

```bash
.venv/bin/python scripts/index_lectures.py \
  "Algorithms" "/absolute/path/to/Algorithms" --json
.venv/bin/python scripts/search_lectures.py \
  "shortest paths" --course "Algorithms" --json
.venv/bin/python scripts/read_lectures.py \
  --course "Algorithms" --source "lecture-01.pdf" --json
```

For the last command, repeat with the returned `next_cursor` while `has_more`
is true. Do not publish real course files unless you own them or have permission
to redistribute them.
