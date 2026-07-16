# Study Workflows

Retrieve evidence across the complete requested scope before drafting. For a
whole lecture, range, or all/every request, call `outline_lectures.py` and
follow `next_cursor` until `has_more` is false. Verify represented records equal
`total_records`, then use bounded reads for selected ranges. Use
`read_lectures.py` only when complete records are required; ranked search
results alone do not prove full coverage.

Disclose the scope-wide `review_needed` count. Native PPTX extraction can
preserve text, notes, tables, and embedded images while still lacking exact
full-slide layout evidence.

## Question Answering

1. Search the user's wording with compact results.
2. Search prerequisite or synonymous terms when evidence is thin.
3. Fetch bounded chunks only for records selected as supporting evidence.
   Follow `next_offset` only when the answer needs more of that record.
4. Answer directly and cite each course-derived claim.
5. Separate optional general knowledge from course evidence.

## Summary

- Cover the lecture's main concepts, definitions, examples, equations, and
  instructor notes.
- Format display equations as mathematics, not monospace programming code.
  Use fenced `math` blocks for PDF study guides so fractions, Greek symbols,
  subscripts, superscripts, vectors, and angle notation render naturally.
  Prefer LaTeX `bmatrix`, `pmatrix`, or `vmatrix` environments for matrices.
  The renderer also converts compact `[[...], [...]]` matrices and transposed
  `[... ]^T` vectors into stacked notation.
  Standalone equations are detected automatically; use `$...$` for inline
  notation when an equation appears inside prose.
- Preserve the taught order when source order is meaningful.
- Include a short source list with slide/page citations.
- State whether visual descriptions were available and whether any records
  remained `review-needed`.

## Cross-Lecture Comparison

- Retrieve from every lecture named by the user.
- Organize similarities, differences, progression, and prerequisites.
- Cite both sides of each comparison.

## Flashcards

Produce atomic question-answer pairs. Include:

```json
{
  "front": "What problem does memoization avoid?",
  "back": "Repeated evaluation of overlapping subproblems.",
  "citation": "[Algorithms, Lecture08.pptx, Slide 27]"
}
```

Avoid cards unsupported by the retrieved course evidence.
Use `references/flashcard-formats.md` as the normalized interchange schema.
Save cited JSON first as the portable source, then run `render_flashcards.py`
to create a self-contained interactive HTML deck by default. Give the user a
readable question/answer list when HTML cannot be displayed. Use
`convert_flashcards.py` only when the user requests CSV or TSV for another
study tool. Preserve citations in every output.

## Practice Exam

- Mix recall, application, and synthesis questions.
- Keep the answer key separate from the questions.
- Cite the answer key, not the question prompt.
- Do not invent course-specific notation or policies.

## Cheat Sheet

- Prioritize definitions, formulas, algorithm steps, comparisons, and common
  pitfalls.
- Keep wording compact but retain citations beside each section.
- Mark topics with incomplete indexed coverage.

## Study Plan

- Retrieve the requested lecture range and prerequisite relationships actually
  supported by those materials.
- Sequence review from prerequisites to applications.
- Assign concrete sessions and active-recall tasks.
- Do not claim personalized mastery or exam weighting without evidence.

## Insufficient Evidence

Search again with alternate terms. If coverage remains insufficient, list the
missing source or concept instead of filling the gap from unstated knowledge.
