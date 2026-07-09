# Backspace-merge, inline math, and rich-text cells

## Why

Three block-editor clauses were specced but not built (each had a scenario for a
sibling behaviour, so `--strict` passed):

- "insert, edit, move, split, **merge**, and delete blocks" — there is no merge:
  Backspace at the start of a non-empty block does nothing, so text can't be
  joined into the previous block. `splitText` has no inverse.
- "LaTeX for both **inline math** and block-level math" — only the block-level
  `latex` block renders; there is no inline `$…$`.
- "cells that may contain **rich text**" — table cells are plain `<input>`
  strings with no emphasis.

## What Changes

- **Merge**: Backspace at offset 0 of a non-empty block joins it into the end of
  the previous block, placing the caret at the join. A single undo step.
- **Inline rich rendering**: one renderer turns a stored source string into
  display HTML — `$…$` → KaTeX inline math, `**bold**`/`*italic*` → emphasis,
  everything else escaped. It renders when a field is unfocused and shows raw
  source when focused (the editor's existing local-DOM-wins pattern), so the
  source is always editable and stored verbatim.
- Paragraph/heading text and table cells use this renderer, satisfying inline
  math and rich-text cells at once. Cells stay plain strings (markdown/LaTeX
  source), so CSV/Excel ingestion is unchanged.

## Non-goals

- A WYSIWYG toolbar or keyboard shortcuts (Ctrl+B) — emphasis is markdown source.
- Changing the block/table data model — rich text is source-in-a-string.
- Inline math inside code blocks (they stay literal).

## Impact

- `block-editor`: the merge, inline-math, and rich-cell clauses gain scenarios.
- Frontend only; no backend or data-model change. Covered by vitest (renderer +
  merge command) and e2e (join two blocks, inline math renders, bold cell).
