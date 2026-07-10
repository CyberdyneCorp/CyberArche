# Document export

## Why
Users need to take a document out of CyberArche — to share a PDF, keep a
Markdown copy, or pull tabular data into a spreadsheet.

## What Changes
- An **Export** button in the document's top-right toolbar opens an export
  dialog offering **PDF**, **Markdown**, and **CSV**.
- **Markdown:** the block tree is serialized to Markdown (headings, lists,
  todos, quotes/callouts, code/mermaid fences, `$$` math, tables, image/embed
  links) and downloaded as a `.md` file.
- **CSV:** the document's table blocks are serialized to CSV (RFC-4180 quoting)
  and downloaded; if the document has no tables, the user is told so.
- **PDF:** the browser's print is used with a print stylesheet that shows only
  the document canvas, so math, mermaid, and images print exactly as rendered —
  no server round-trip.

## Impact
- New spec: `document-export`. Entirely client-side (`lib/editor/export.ts`,
  `ExportDialog.svelte`, a print stylesheet) — no backend or data-model changes.
- Limitation: uploaded images referenced in Markdown keep their served
  (membership-gated) URL rather than being inlined.
