# collections Specification

## ADDED Requirements

### Requirement: Embed a collection in a document

The system SHALL let a member embed a collection inside a document as a block.
Inserting a database block SHALL create a collection in the document's workspace
and reference it from the block; the block SHALL render the collection's views —
table, board, gallery, and calendar — inline, with the same editing as the
full-page collection, and SHALL be read-only when the document is read-only. The
embedded collection SHALL be the same kind of collection as a full-page one, so
every collection capability (typed properties, formulas, relations, rollups,
reminders, filters, sorts, and bulk actions) applies to it.

#### Scenario: Insert an inline database

- **GIVEN** a member editing a document
- **WHEN** they insert a database block
- **THEN** the system SHALL create a collection and embed a view of it in the
  document, editable inline

#### Scenario: Existing inline databases keep working

- **GIVEN** a document that already contains a legacy database block
- **WHEN** the document is opened
- **THEN** that block SHALL continue to render
