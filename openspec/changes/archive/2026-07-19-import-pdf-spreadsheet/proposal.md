# Import PDF, and CSV/Excel as a database

## Why

Import covers text formats but not PDFs or spreadsheets. A PDF should import as a
document; a CSV/Excel sheet should become a real database (a collection) — the
natural way to bring tabular data in and immediately use formulas, filters, and
the other collection features.

## What Changes

- Accept `.pdf` and import it as a document (extracted text as blocks).
- Accept `.csv` / `.xlsx` and import the sheet as a new collection: the first
  column becomes each row's title and the remaining columns become typed
  properties (numeric columns inferred as numbers); a new document embeds a view
  of that collection via a `collection_view` block.
- Surface the new formats on the import control.

## Impact

- Affected specs: `document-model`.
- Affected code: FileExtractor `extract_table` (header + rows); ImportUseCases
  (spreadsheet → collection + embedding doc, compose CollectionUseCases; route
  .pdf → blocks); wiring; frontend accept list + label. Row count capped.
