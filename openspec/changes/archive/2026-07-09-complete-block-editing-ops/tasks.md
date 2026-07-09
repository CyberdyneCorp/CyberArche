# Tasks

## 1. Merge
- [x] 1.1 EditableText: Backspace at caret 0 on non-empty text -> onmergeback
- [x] 1.2 Editor VM `mergeWithPrevious(id)`: append text to previous, remove, caret at join, one undo step
- [x] 1.3 Wire TextBlocks; vitest for the merge command (incl. undo)

## 2. Inline rich renderer
- [x] 2.1 `renderInline(text)`: escape, then `$…$` -> KaTeX inline, `**b**`/`*i*` -> strong/em; invalid math -> inline error span
- [x] 2.2 EditableText `rich` mode: render HTML when unfocused, raw source when focused; oninput reads source
- [x] 2.3 vitest for renderInline (math, bold, italic, escaping, invalid math)

## 3. Wire paragraphs + cells
- [x] 3.1 Paragraph/heading text uses rich rendering
- [x] 3.2 Table cells become rich contenteditable storing source strings
- [x] 3.3 e2e: merge two blocks; inline `$…$` renders; a `**bold**` cell renders
