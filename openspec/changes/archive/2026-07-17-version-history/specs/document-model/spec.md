# document-model Specification

## MODIFIED Requirements

### Requirement: Version snapshots

The system SHALL periodically persist an immutable snapshot of a document's
content, and SHALL allow listing, naming (an optional label), restoring, and
**diffing** snapshots. Restoring SHALL replace the current content and is itself
recorded as a new snapshot. A diff SHALL report the block-level changes between
two snapshots, or between a snapshot and the current document state. All
operations SHALL be access-scoped to callers who may view (list/diff) or edit
(restore) the document.

#### Scenario: Name a version

- **WHEN** a snapshot is recorded or renamed with a label
- **THEN** the label SHALL be stored and returned when listing versions

#### Scenario: Diff two versions

- **GIVEN** two snapshots of a document
- **WHEN** a caller requests a diff between them
- **THEN** the system SHALL return the blocks added, removed, and modified
  between them

#### Scenario: Diff a version against the current document

- **WHEN** a caller diffs a snapshot with no second snapshot given
- **THEN** the system SHALL compare it against the document's current content

#### Scenario: Restore records a new snapshot

- **GIVEN** a prior snapshot
- **WHEN** an editor restores it
- **THEN** the current content SHALL be replaced and a new snapshot SHALL record
  the restore
