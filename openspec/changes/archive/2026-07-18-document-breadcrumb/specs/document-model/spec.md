# document-model Specification

## ADDED Requirements

### Requirement: Document breadcrumb path

The system SHALL provide the ancestor path of a document as an ordered list of
crumbs so the client can show where the document lives and let the user navigate
upward. The path SHALL begin with the document's workspace, then its teamspace
when it belongs to one, then its folders from the outermost to the innermost when
it is filed in a folder, then its ancestor documents from the topmost ancestor
down to its immediate parent, and finally the document itself. Each crumb SHALL
carry a kind (workspace, teamspace, folder, or document), an id, and a label.
Requesting the path SHALL require view access to the document and be scoped to
the caller's tenant.

#### Scenario: Path of a nested document

- **GIVEN** a document filed in a folder within a teamspace and nested under a
  parent document
- **WHEN** its path is requested by a member with view access
- **THEN** the crumbs SHALL be ordered workspace, teamspace, folder(s), ancestor
  document(s), then the document, each with its label

#### Scenario: Path of a root document

- **GIVEN** a document at the workspace root with no teamspace or folder
- **WHEN** its path is requested
- **THEN** the crumbs SHALL be the workspace followed by the document

#### Scenario: Access required

- **WHEN** a caller without view access requests a document's path
- **THEN** the system SHALL refuse the request
