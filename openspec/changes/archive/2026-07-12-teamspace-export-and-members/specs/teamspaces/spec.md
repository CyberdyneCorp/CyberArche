# teamspaces Specification

## ADDED Requirements

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
