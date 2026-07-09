# permissions-sharing Specification

## MODIFIED Requirements

### Requirement: Roles on workspaces and documents
The system SHALL support the roles `owner`, `editor`, `commenter`, and `viewer`
on workspaces, teamspaces, and documents. For a document in a teamspace, a
user's effective role SHALL be the strongest of their workspace role, their role
in the document's teamspace, and any document-level grant, except that a
document-level grant SHALL always override the inherited roles. A document with
no teamspace SHALL be private: its effective role SHALL be any document-level
grant, otherwise `owner` for the document's creator, otherwise none — a
workspace role SHALL NOT grant access to a teamspace-less document.

#### Scenario: Inherited access within a teamspace
- **WHEN** a user has `editor` on a workspace and no document-level override
- **AND** the document belongs to a teamspace
- **THEN** the user SHALL have `editor` on that document

#### Scenario: A private document is creator-only
- **GIVEN** a document with no teamspace created by user A
- **WHEN** user B, an editor of the workspace, accesses it
- **THEN** user B SHALL have no access
- **AND** user A SHALL have owner access

#### Scenario: A grant reaches a private document
- **WHEN** the creator grants user B `viewer` on a private document
- **THEN** user B SHALL have `viewer` on it

#### Scenario: Document-level override
- **WHEN** a document grants a user `viewer` while the workspace grants `editor`
- **THEN** the more specific document grant SHALL apply for that document

#### Scenario: Teamspace membership grants access
- **WHEN** a user has no workspace role but is an `editor` of the document's teamspace
- **THEN** the user SHALL have `editor` on that document
