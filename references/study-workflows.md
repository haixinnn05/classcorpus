# Study Workflows

Retrieve evidence across the complete requested scope before drafting. If a
lecture range is requested, search each lecture or source represented in that
range rather than relying on one top result.

## Question Answering

1. Search the user's wording.
2. Search prerequisite or synonymous terms when evidence is thin.
3. Answer directly and cite each course-derived claim.
4. Separate optional general knowledge from course evidence.

## Summary

- Cover the lecture's main concepts, definitions, examples, equations, and
  instructor notes.
- Preserve the taught order when source order is meaningful.
- Include a short source list with slide/page citations.
- State whether visual descriptions were available.

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
