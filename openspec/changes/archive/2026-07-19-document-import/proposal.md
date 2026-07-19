# Import documents from Markdown, Notion export, and .docx

## Why

There is no way to bring existing content in. Import is the fastest way for a new
team to move onto CyberArche — and today an uploaded Markdown file is flattened
to bare paragraphs (headings/lists/tables lost), with no .docx or Notion-export
support at all.

## What Changes

- A structured Markdown → blocks converter (headings, bullet/numbered lists,
  to-dos, quotes, code/mermaid fences, tables, dividers, images) in the domain,
  used when importing Markdown (and to properly extract uploaded `.md`).
- Import a single `.md` / `.markdown` / `.txt` or `.docx` file into a new private
  document, titled from its first heading or filename.
- Import a Notion `.zip` export: one document per Markdown file, folder nesting
  preserved as parent documents, Notion's id suffixes stripped from titles.
- An import endpoint and a sidebar Import affordance.

## Impact

- Affected specs: `document-model`.
- Affected code: a domain markdown→blocks module; `FileExtractor` (.md via the
  new converter, add .docx via `python-docx`); an import use case; the import
  router; frontend import client + trigger. New dependency: `python-docx`.
