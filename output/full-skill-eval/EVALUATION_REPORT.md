# ClassCorpus Full-Skill Evaluation

**Corpus:** Five PHYS 1401 lecture PDFs  
**Source:** `/Users/haixinwu/Downloads/physics`  
**Records:** 116 pages  
**ClassCorpus:** 0.3.0

## Final State

| Metric | Result |
|---|---:|
| Sources ready | 5 / 5 |
| Indexed records | 116 |
| Review-needed records | 0 |
| Visually reviewed records | 6 |
| OCR complete | 116 / 116 |
| OCR failures | 0 |
| Hashing embeddings | 116 / 116 |
| Source PDFs modified | 0 |

## Capability Results

| Tool or capability | Result | Evidence |
|---|---|---|
| `classcorpus doctor` | PASS | Required checks passed in an isolated writable data directory; version reported 0.3.0. |
| `index_lectures.py` / CLI index | PASS | Indexed 5 PDFs and 116 pages with zero failures; repeat sync skipped all 5 unchanged files. |
| `classcorpus status` | PASS | Reported source health, review state, OCR state, and embedding identity correctly. |
| Compact adaptive search | PASS | Three-result, 600-token search returned the expected Lecture 5 pages in 457 estimated tokens. |
| Standard and full search | PASS | Compact and lossless full payloads returned canonical citations and expected fields. |
| Typo suggestions | PASS | `accleratoin` returned no fabricated result and suggested `acceleration` and `accelerating`. |
| Source and ordinal filters | PASS | Exact Lecture 5 page 20 selection returned one matching record. |
| Bounded record reads | PASS | A 100-character read returned `next_offset: 100`; the next read resumed without a gap. |
| Coverage outline | PASS | A 700-token budget required 22 continuations and represented exactly 116 of 116 records. |
| Exhaustive reads | PASS | Seven-record pages advanced with an opaque cursor from ordinal 7 to ordinal 8. |
| Hashing embeddings | PASS | Built 128-dimensional provider-neutral embeddings for all 116 records. |
| Semantic retrieval | PASS | Hybrid retrieval ranked two-dimensional vector pages first and retained extraction warnings. |
| Vision queue | PASS | Prioritized all five extraction-risk pages and returned full-page render paths. |
| Visual inspection | PASS | Inspected all five risk pages plus one representative Lecture 2 page. |
| Store visual descriptions | PASS | Stored 6 descriptions; review-needed fell from 5 to 0 and descriptions became searchable. |
| Embedding invalidation | PASS | Visual and OCR updates invalidated stale vectors; rebuilding restored 116 of 116. |
| Local OCR | PASS | Installed optional adapter and Tesseract 5.5.2; processed all 116 pages with zero failures. |
| OCR idempotence | PASS | A repeat OCR run processed 0 records. |
| Flashcard conversion | PASS | Exported 10 cited cards to CSV and TSV; CSV round-trip preserved all citations. |
| Overwrite protection | PASS | Existing flashcard output was refused without `--overwrite`. |
| Study workflows | PASS | Produced a summary, comparison, formula sheet, cheat sheet, practice exam, answer key, and study plan. |
| PDF renderer | PASS | Produced a polished, text-extractable 5-page PDF with display equations and citations. |
| PowerPoint review | NOT APPLICABLE | Correctly returned zero items because the supplied corpus contains only PDFs. |
| Course removal guard | PASS | Refused removal without `--confirm`. |
| Confirmed course removal | PASS | Removed only a generated `REMOVE-SMOKE` course; the PHYS1401 course and source PDFs remained intact. |
| Repository regression | PASS | 189 tests passed, Ruff passed, and benchmark extraction/retrieval/token-efficiency gates passed. |

## Findings

1. The existing virtual environment contained stale 0.2.0 package metadata even though the checkout is 0.3.0. Reinstalling the local editable package corrected it.
2. OCR is strong on typed lecture text but noisy on handwriting and equations. Visual descriptions are the better evidence source for those pages.
3. The bundled Poppler rasterizer entered a fontconfig cache loop in the sandbox. PyMuPDF rendered all final PDF pages correctly and was used for visual verification.
4. The five source PDFs remain read-only and unchanged. All generated state lives outside the source folder.

## Generated Artifacts

- `PHYS1401_Lectures_1-5_Showcase.pdf`
- `PHYS1401_Lectures_1-5_Showcase.md`
- `PHYS1401_flashcards.json`
- `PHYS1401_flashcards.csv`
- `PHYS1401_flashcards.tsv`
- `PHYS1401_flashcards-roundtrip.json`
- `visual-descriptions.json`
