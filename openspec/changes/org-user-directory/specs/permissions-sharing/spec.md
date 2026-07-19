# permissions-sharing Specification (delta)

## MODIFIED Requirements

### Requirement: Invite collaborators
An authorized user SHALL invite other users (by CyberdyneAuth identity) to a
workspace or document with a chosen role. The invite UI SHALL let the inviter
pick the user from the organization directory (searching by email); when the
directory is unavailable or the organization has no directory, the UI SHALL
fall back to entering a raw CyberdyneAuth user id.

#### Scenario: Invite as commenter
- **WHEN** an owner invites a user as `commenter`
- **THEN** the invited user SHALL be able to view and comment but not edit

#### Scenario: Invite by picking from the directory
- **WHEN** an owner searches the org directory in the share dialog and selects
  a user
- **THEN** the invite SHALL target the selected user's id without the inviter
  typing it

#### Scenario: Fallback to raw id
- **WHEN** the org directory returns an error
- **THEN** the share dialog SHALL still allow inviting by raw user id
