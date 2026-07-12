# teamspaces Specification

## Purpose
TBD - created by archiving change add-teamspaces-and-agent-editing. Update Purpose after archive.
## Requirements
### Requirement: Teamspaces group documents inside a workspace
The system SHALL allow an authorized user to create a named teamspace within a
workspace, and SHALL allow documents to belong to at most one teamspace.

#### Scenario: Create a teamspace
- **WHEN** a workspace editor creates a teamspace with a name
- **THEN** the teamspace SHALL belong to that workspace
- **AND** the creator SHALL become a member with the `owner` role

#### Scenario: Place a document in a teamspace
- **WHEN** a document is created with a teamspace
- **THEN** the document SHALL be listed under that teamspace
- **AND** the teamspace SHALL belong to the document's workspace

#### Scenario: Reject a cross-workspace teamspace
- **WHEN** a document is placed in a teamspace of another workspace
- **THEN** the system SHALL reject it with a validation error

### Requirement: Teamspace membership
The system SHALL let a teamspace owner add and remove members with a role, and
SHALL list a teamspace's members.

#### Scenario: Add a member
- **WHEN** a teamspace owner adds a user as `editor`
- **THEN** the user SHALL appear among the teamspace's members with that role

#### Scenario: Only owners manage membership
- **WHEN** a non-owner member attempts to add another member
- **THEN** the system SHALL deny the request

### Requirement: Teamspace membership grants document access
A user's effective role on a document in a teamspace SHALL be the strongest of
their workspace role, their teamspace role, and any document-level grant.

#### Scenario: Teamspace member reads a document they could not otherwise see
- **WHEN** a user has no workspace role but is a teamspace `editor`
- **THEN** the user SHALL be able to view and edit documents in that teamspace

#### Scenario: Non-member is denied
- **WHEN** a user is neither a workspace member, a teamspace member, nor a
  document grantee
- **THEN** access to the teamspace's documents SHALL be denied

### Requirement: Listing teamspaces
The system SHALL list the teamspaces of a workspace that the caller may see,
and SHALL list the documents belonging to a teamspace.

#### Scenario: List visible teamspaces
- **WHEN** a user lists a workspace's teamspaces
- **THEN** the system SHALL return the teamspaces the user may view

### Requirement: Delete a teamspace
The system SHALL let a teamspace owner delete a teamspace. Deleting a teamspace
SHALL move every document in it — including documents grouped under its folders —
to Trash, where they remain recoverable, and SHALL remove the teamspace's
folders. A user who is not an owner of the teamspace SHALL NOT be able to delete
it.

#### Scenario: Owner deletes a teamspace
- **GIVEN** a teamspace with documents, some grouped in folders
- **WHEN** an owner deletes the teamspace
- **THEN** the teamspace SHALL no longer be listed
- **AND** its documents SHALL be moved to Trash
- **AND** its folders SHALL be removed

#### Scenario: A trashed document from a deleted teamspace can be restored
- **GIVEN** a teamspace was deleted and its documents moved to Trash
- **WHEN** the owner restores one of those documents
- **THEN** the document SHALL exist again outside the trash

#### Scenario: A non-owner cannot delete a teamspace
- **WHEN** a member who is not an owner attempts to delete the teamspace
- **THEN** the request SHALL be refused
- **AND** the teamspace SHALL still be listed

### Requirement: Invite and manage teamspace members from the app

The web app SHALL let a teamspace owner manage its members from the teamspace's
context menu: invite a user with a role (viewer, editor, or owner), see the
current members, and remove a member. An editor or owner SHALL be able to author
documents in the teamspace.

#### Scenario: Invite a member

- **WHEN** an owner opens "Manage members", enters a user, picks the editor role,
  and confirms
- **THEN** that user SHALL become a member of the teamspace with the editor role
- **AND** SHALL be able to author its documents

#### Scenario: Remove a member

- **WHEN** an owner removes a member
- **THEN** that user SHALL no longer be a member of the teamspace

