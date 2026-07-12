# permissions-sharing Specification

## Purpose

Roles, invites, document-level overrides, shareable links, comments, and uniform enforcement across every inbound surface.
## Requirements
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

### Requirement: Invite collaborators
An authorized user SHALL invite other users (by CyberdyneAuth identity) to a
workspace or document with a chosen role.

#### Scenario: Invite as commenter
- **WHEN** an owner invites a user as `commenter`
- **THEN** the invited user SHALL be able to view and comment but not edit

### Requirement: Shareable links
The system SHALL support shareable links scoped to a permission level
(`view`, `comment`, `edit`), which MAY be revoked and MAY expire.

#### Scenario: Open a view link
- **WHEN** a recipient opens a valid `view` share link
- **THEN** the system SHALL grant read-only access to the shared document

#### Scenario: Revoke a link
- **WHEN** an owner revokes a share link
- **THEN** subsequent use of that link SHALL be denied

### Requirement: Enforcement across all surfaces
Permission checks SHALL be enforced uniformly across the HTTP API, the realtime
CRDT channel, and the MCP tools, so no surface can bypass access control.

#### Scenario: Consistent denial
- **WHEN** a caller lacks edit permission
- **THEN** edit attempts SHALL be denied whether made via HTTP, realtime, or MCP

### Requirement: Comments
The system SHALL allow commenters and above to attach comments to blocks and to
resolve them.

#### Scenario: Comment on a block
- **WHEN** a commenter adds a comment to a block
- **THEN** the comment SHALL be visible to other participants on that block

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

### Requirement: Comment mentions notify workspace members

The system SHALL create a `mention` notification when a comment mentions a user
who is a member of the document's workspace, identifying the comment's author and
the document. A mention is written in the comment body as an at-sign followed by
the user id in brackets. The system SHALL NOT notify the author for mentioning
themselves, and SHALL NOT create a notification for a mentioned user who is not a
member of the document's workspace.

#### Scenario: A mention notifies a member

- **WHEN** a member adds a comment that mentions another workspace member
- **THEN** the mentioned member SHALL receive a mention notification for that
  document

#### Scenario: Non-members and self-mentions are ignored

- **WHEN** a comment mentions the author, or a user who is not a workspace member
- **THEN** no notification SHALL be created for that mention

