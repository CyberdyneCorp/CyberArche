# document-export Specification

## ADDED Requirements
### Requirement: Export a document
The editor SHALL let a user export the open document from a control in the
document toolbar, choosing a format: PDF, Markdown, or CSV.

#### Scenario: Open the export dialog
- **WHEN** the user activates Export in the document toolbar
- **THEN** a dialog SHALL offer PDF, Markdown, and CSV

### Requirement: Markdown export
Markdown export SHALL serialize the document (title and blocks) to Markdown —
headings, lists, to-dos, quotes/callouts, code and mermaid fences, display math,
tables, and image/embed links — and download it as a text file.

#### Scenario: Download Markdown
- **WHEN** the user exports as Markdown
- **THEN** a `.md` file SHALL be downloaded containing the document's content

### Requirement: CSV export of tables
CSV export SHALL serialize the document's table blocks to CSV with correct
quoting, and download it. When the document has no tables, the user SHALL be
informed and no file produced.

#### Scenario: Download tables as CSV
- **GIVEN** a document with a table
- **WHEN** the user exports as CSV
- **THEN** a `.csv` file SHALL be downloaded with the table's rows

#### Scenario: No tables to export
- **GIVEN** a document with no tables
- **WHEN** the user exports as CSV
- **THEN** the user SHALL be told there is nothing to export

### Requirement: PDF export
PDF export SHALL produce a print-ready rendering of the document showing only its
content (not the app chrome), preserving rendered math, diagrams, and images.

#### Scenario: Export as PDF
- **WHEN** the user exports as PDF
- **THEN** the document content SHALL be presented for saving as a PDF, without
  the sidebar, toolbar, or panels
