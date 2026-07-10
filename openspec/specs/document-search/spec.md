# document-search Specification

## Purpose
TBD - created by archiving change wikilinks-search-palette. Update Purpose after archive.
## Requirements
### Requirement: Search documents in a workspace
The system SHALL let a caller search a workspace's documents by title and return
matches the caller may access.

#### Scenario: Title search returns matches
- **WHEN** a member searches with a query
- **THEN** documents whose title matches SHALL be returned

#### Scenario: Search respects access
- **WHEN** a caller searches
- **THEN** only documents in workspaces they can access SHALL be returned

### Requirement: Command palette
The app SHALL provide a keyboard-invoked command palette (Cmd/Ctrl+K) to search
documents by title and open one, or create a new document.

#### Scenario: Jump to a document
- **WHEN** the user opens the palette, types a title, and selects a result
- **THEN** that document SHALL open

#### Scenario: Create from the palette
- **WHEN** the user chooses to create a new document from the palette
- **THEN** a new document SHALL be created and opened

