# Citation Rules

Use the `citation` field returned by `search_lectures.py` without rewriting its
course, source file, or one-based ordinal.

Canonical forms:

```text
[Algorithms, Lecture08.pptx, Slide 27]
[Algorithms, handout.pdf, Page 3]
[Algorithms, Lecture08.vtt, 14:32]
[Algorithms, seminar.srt, 01:14:32.500]
```

Transcript citations use the exact cue start time. Hours are included only
when nonzero, and milliseconds only when nonzero. Keep the returned timestamp
unchanged; use the record's one-based `ordinal` for `read` and `inspect`.

## Grounding

- Place a citation immediately after the sentence or bullet it supports.
- Cite every factual claim presented as coming from the course.
- Use multiple citations when a claim combines multiple records.
- Keep comparisons traceable by citing each side independently.
- Do not cite a record that merely mentions a keyword but does not support the
  claim.
- If retrieved records conflict, describe the conflict and cite both.
- If evidence is missing, say that the indexed materials do not establish the
  answer.
- Label any general explanation added by the host agent as outside the indexed
  course materials.

## Source Access

Preserve `source_path` internally. When the environment supports opening local
files, offer the exact original file and slide/page location rather than
copying or redistributing the source.

Before presenting a citation for verification, run:

```text
classcorpus inspect COURSE SOURCE ORDINAL --json
```

Disclose non-current `source_verification`, extraction warnings, and missing
visual previews. Synchronize changed or parser-stale sources before relying on
their stored evidence.
