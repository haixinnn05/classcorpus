# No-LibreOffice PowerPoint Handling

## Goal

ClassCorpus must never invoke, require, recommend, or detect LibreOffice or
`soffice`. PowerPoint indexing must remain local, open source, cross-platform,
and useful without pretending that pure Python can reproduce PowerPoint's
pixel-accurate rendering.

## Decision

Use native PPTX/OOXML extraction as the default PowerPoint path:

1. Extract all accessible text, speaker notes, tables, relationships, and
   structural evidence with `python-pptx` and OOXML.
2. Extract embedded raster images byte-for-byte as local visual assets.
3. Preserve asset geometry and source metadata so an agent can understand what
   each image belongs to.
4. Mark charts, SmartArt, equations, OLE objects, and layout-dependent slides
   `review-needed` when no complete visual representation is available.
5. Let users export a lecture to PDF and index that PDF when pixel-accurate
   visual review is required.

ClassCorpus will not substitute a low-fidelity homemade slide renderer and call
it accurate.

## Why Not Other Renderers

- Apple Keynote and Microsoft PowerPoint are proprietary and platform-specific.
- Aspose.Slides and similar libraries are commercial dependencies.
- Browser PPTX renderers have incomplete PowerPoint compatibility and would add
  Node/browser infrastructure to a portable Python skill.
- `unoconv` and many `pptx-to-image` wrappers still depend on LibreOffice.

These may be documented as external user workflows, but none belongs in the
ClassCorpus runtime.

## Data Model

Add a `VisualAsset` record:

```text
path
kind
shape_name
content_type
left
top
width
height
```

`SlideRecord` carries an ordered tuple of assets. SQLite stores assets in a
separate `visual_assets` table keyed to the slide record:

```sql
visual_assets(
    id,
    slide_id,
    asset_index,
    path,
    kind,
    shape_name,
    content_type,
    left,
    top,
    width,
    height
)
```

The unique key `(slide_id, asset_index)` preserves source order. Geometry uses
PowerPoint EMUs without lossy conversion.

## Extraction

For every picture shape, including pictures inside groups:

- read image bytes from the existing PPTX relationship;
- derive the extension from the image content type;
- write the bytes atomically under the source's versioned generation
  directory;
- record shape name and geometry;
- add the `embedded-image` extraction reason.

ClassCorpus must deduplicate repeated package blobs by content hash within one
slide while retaining every shape occurrence and its geometry. The same path
may therefore be referenced by multiple asset records.

Charts, diagrams, equations, and embedded objects remain represented by their
OOXML text census and extraction reasons. ClassCorpus must not rasterize or
claim to visually inspect them.

## Vision Queue

PDF records continue to provide full-page renders through PyMuPDF.

PPTX records provide zero or more embedded visual assets:

- Queue items expose `render_path` for a full PDF page when available.
- Queue items expose ordered `asset_paths` and asset metadata for PPTX images.
- A slide with review reasons but no viewable render or asset reports
  `visual-source-unavailable`.
- The agent may describe embedded assets after user consent, but must disclose
  that overall PowerPoint layout was not visually verified.

Storing a description marks a record `visually-reviewed` only when the agent
actually received at least one render or asset. Layout-dependent reasons remain
in `extraction_reasons`.

## Generated-Data Lifecycle

Visual assets live in the same versioned generated-data area as PDF renders.
Source replacement, source removal, course removal, failed publication, and
pending-deletion recovery must account for both render paths and asset paths.
Lecture source files remain untouched.

## User-Supplied PDF Workflow

When a user needs exact charts, SmartArt, equations, or slide layout:

1. Export the PowerPoint to PDF using any tool they choose.
2. Place the PDF in the indexed course folder.
3. Synchronize the course.
4. Use the PDF pages as visual evidence and cite the PDF page.

ClassCorpus does not automate the export or invoke desktop software.

## Error Handling

- A failed image extraction must not discard successfully extracted text.
- The affected slide is `review-needed` with an actionable warning.
- Unsupported image content types remain recorded as unavailable assets rather
  than being silently ignored.
- A chart-only or equation-only slide remains searchable through native text
  and explicitly reports that no visual source is available.

## Documentation

Remove every statement that LibreOffice is required or supported. The README
and skill must explain:

- PPTX text, notes, tables, and embedded images are handled locally.
- ClassCorpus does not fully render PowerPoint slides.
- PDF is the supported path for pixel-accurate visual inspection.
- No desktop application or external conversion command is invoked.

## Testing

Tests must prove:

- no production or documentation reference to `LibreOffice`, `soffice`, or
  `unoconv` remains;
- indexing never calls a subprocess for PPTX handling;
- embedded image bytes survive extraction exactly;
- multiple image shapes preserve order and geometry;
- grouped pictures are discovered;
- repeated image blobs are deduplicated without losing shape occurrences;
- chart/equation/SmartArt/OLE slides remain `review-needed`;
- review-needed slides without assets return `visual-source-unavailable`;
- visual descriptions cannot mark a PPTX record reviewed when no viewable
  asset was supplied;
- replacement and removal clean both renders and assets;
- PDF extraction and rendering remain unchanged;
- macOS, Windows, and Linux tests use the same code path.

## Acceptance Criteria

The change is complete when:

1. `rg -i "libreoffice|soffice|unoconv"` finds no production or public
   documentation references.
2. PPTX indexing passes while `subprocess.run` is patched to fail on every
   invocation.
3. Generated PPTX fixtures prove exact text, notes, tables, embedded-image
   bytes, geometry, and uncertainty reasons.
4. The real acceptance workflow indexes PPTX files without spawning a process.
5. PDF pages still render and enter the vision queue.
6. All automated and cross-platform release checks pass.
