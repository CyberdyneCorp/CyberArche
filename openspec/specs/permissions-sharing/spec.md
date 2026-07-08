# permissions-sharing Specification

## Purpose

Roles, invites, document-level overrides, shareable links, comments, and uniform enforcement across every inbound surface.

## Requirements

### Requirement: Roles on workspaces and documents
The system SHALL support the roles `owner`, `editor`, `commenter`, and `viewer`
on both workspaces and documents, where a document inherits access from its
workspace unless overridden.

#### Scenario: Inherited access
- **WHEN** a user has `editor` on a workspace and no document-level override
- **THEN** the user SHALL have `editor` on documents in that workspace

#### Scenario: Document-level override
- **WHEN** a document grants a user `viewer` while the workspace grants `editor`
- **THEN** the more specific document grant SHALL apply for that document

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
