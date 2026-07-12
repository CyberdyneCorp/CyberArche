# templates Specification

## ADDED Requirements

### Requirement: Save a document as a template

The system SHALL let a workspace member save a document as a named page template
in that workspace, capturing the document's current block content. Saving SHALL
require edit rights on the document.

#### Scenario: Save as template

- **WHEN** a member saves a document as a template with a name
- **THEN** a template SHALL be created in the workspace holding that document's
  blocks

### Requirement: Create a document from a template

The system SHALL let a member create a new document pre-filled with a template's
blocks, placed in a chosen teamspace or the private space. The new document's
blocks SHALL have fresh ids so they do not collide with the template's source.

#### Scenario: New from template

- **WHEN** a member creates a document from a template
- **THEN** a new document SHALL be created containing the template's blocks

### Requirement: List and delete templates

The system SHALL let a workspace member list the workspace's templates, and let
the template's creator or a workspace owner delete one.

#### Scenario: Delete a template

- **WHEN** the creator deletes a template
- **THEN** it SHALL no longer appear in the workspace's templates
