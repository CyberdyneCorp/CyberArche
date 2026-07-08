# document-model Specification

## ADDED Requirements

### Requirement: Documents may belong to a teamspace
A document SHALL optionally reference a teamspace of its own workspace, and the
system SHALL list a workspace's documents by teamspace.

#### Scenario: Create a document in a teamspace
- **WHEN** a document is created with a teamspace of the same workspace
- **THEN** the document SHALL record that teamspace

#### Scenario: Documents without a teamspace remain workspace-level
- **WHEN** a document is created without a teamspace
- **THEN** it SHALL appear in the workspace's document tree, not under a teamspace
