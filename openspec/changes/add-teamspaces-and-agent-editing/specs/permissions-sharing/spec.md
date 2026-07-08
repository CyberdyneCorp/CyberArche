# permissions-sharing Specification

## MODIFIED Requirements

### Requirement: Roles on workspaces and documents
The system SHALL support the roles `owner`, `editor`, `commenter`, and `viewer`
on workspaces, teamspaces, and documents. A user's effective role on a document
SHALL be the strongest of their workspace role, their role in the document's
teamspace (if any), and any document-level grant, except that a document-level
grant SHALL always override the inherited roles.

#### Scenario: Inherited access
- **WHEN** a user has `editor` on a workspace and no document-level override
- **THEN** the user SHALL have `editor` on documents in that workspace

#### Scenario: Document-level override
- **WHEN** a document grants a user `viewer` while the workspace grants `editor`
- **THEN** the more specific document grant SHALL apply for that document

#### Scenario: Teamspace membership grants access
- **WHEN** a user has no workspace role but is an `editor` of the document's teamspace
- **THEN** the user SHALL have `editor` on that document
