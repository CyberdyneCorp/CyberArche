# permissions-sharing Specification

## ADDED Requirements

### Requirement: Shared-with-me listing
The system SHALL list, for the calling user, every document reachable only
through a document-level grant — that is, documents the user can open but
which are not in a workspace or teamspace they belong to. Trashed documents
SHALL be excluded. The listing SHALL be scoped to the caller: a grant issued
to another user SHALL NOT appear.

#### Scenario: A grant surfaces the document
- **GIVEN** a document in a workspace the user is not a member of
- **WHEN** the owner grants that user `viewer` on the document
- **THEN** the document SHALL appear in the user's shared-with-me listing

#### Scenario: Workspace members do not see their own documents as shared
- **GIVEN** a user with a workspace role covering a document
- **WHEN** the user requests the shared-with-me listing
- **THEN** the document SHALL NOT appear, because access is inherited, not granted

#### Scenario: Revoked and trashed documents disappear
- **WHEN** a granted document is trashed
- **THEN** it SHALL NOT appear in the shared-with-me listing

#### Scenario: Grants are per-user
- **GIVEN** a document granted to user A
- **WHEN** user B requests the shared-with-me listing
- **THEN** the document SHALL NOT appear for user B

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
