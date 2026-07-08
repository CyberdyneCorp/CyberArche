# teamspaces Specification

## ADDED Requirements

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
