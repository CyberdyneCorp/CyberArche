# document-search Specification

## MODIFIED Requirements

### Requirement: Search documents in a workspace

The system SHALL let a caller search a workspace's documents by **title and
block content**, returning matches the caller may access. Each hit SHALL
indicate whether the match was in the title or the content and, for a content
match, SHALL include a short surrounding snippet.

#### Scenario: Title search returns matches

- **WHEN** a member searches with a query that appears in a document's title
- **THEN** that document SHALL be returned, marked as a title match

#### Scenario: Content search returns matches with a snippet

- **WHEN** a member searches with a query that appears in a document's block text
  but not its title
- **THEN** that document SHALL be returned, marked as a content match
- **AND** the result SHALL include a snippet of the surrounding text

#### Scenario: Search respects access

- **WHEN** a caller searches
- **THEN** only documents the caller may view SHALL be returned, whether the
  match was in the title or the content

## ADDED Requirements

### Requirement: Ask the workspace (RAG answer)

The search experience SHALL let a member ask a natural-language question and
receive an answer grounded in the workspace's ingested knowledge, via the
existing RAG query capability. The answer SHALL be scoped to the caller's
workspace and SHALL require workspace membership.

#### Scenario: Ask a question from search

- **GIVEN** a member of a workspace with ingested knowledge
- **WHEN** the member asks a question from the search UI
- **THEN** the system SHALL return a RAG-grounded answer for that workspace
