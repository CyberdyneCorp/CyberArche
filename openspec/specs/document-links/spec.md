# document-links Specification

## Purpose
TBD - created by archiving change wikilinks-search-palette. Update Purpose after archive.
## Requirements
### Requirement: Wikilink references between documents
The editor SHALL support `[[Document Name]]` references. While typing, `[[` SHALL
open an autocomplete of documents by title; choosing one inserts `[[Title]]`. A
wikilink SHALL render as a link that resolves, case-insensitively, to the
workspace document whose title matches, and activating it SHALL open that
document. A name that matches no document SHALL render as a distinct unresolved
link.

#### Scenario: Insert a wikilink via autocomplete
- **WHEN** the user types `[[` and picks a document from the suggestions
- **THEN** `[[that document's title]]` SHALL be inserted

#### Scenario: A wikilink resolves to its document
- **GIVEN** a document titled "Calculus Introduction" exists in the workspace
- **WHEN** another document contains `[[Calculus Introduction]]`
- **THEN** it SHALL render as a link that opens "Calculus Introduction"

#### Scenario: An unresolved wikilink is distinguished
- **WHEN** a wikilink names a document that does not exist
- **THEN** it SHALL render as an unresolved link, visually distinct from a
  resolved one

### Requirement: Backlinks
The system SHALL report, for a document, the other documents in its workspace
whose content references it via a wikilink to its title, and the editor SHALL
surface these backlinks.

#### Scenario: A referencing document appears as a backlink
- **GIVEN** document A contains `[[B]]` and B is a document
- **WHEN** viewing B's backlinks
- **THEN** A SHALL be listed

