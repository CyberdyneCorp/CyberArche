# workspace-members Specification (delta)

## ADDED Requirements

### Requirement: List workspace members
The system SHALL expose `GET /api/v1/workspaces/{workspace_id}/members`
returning every workspace membership (user id and role, with email and avatar
enriched from the org directory when available). Any user with a role on the
workspace SHALL be able to list its members.

#### Scenario: Member lists members
- **WHEN** a workspace `viewer` calls the members listing
- **THEN** all memberships SHALL be returned with user id and role

#### Scenario: Directory enrichment is best-effort
- **WHEN** the org directory is unavailable
- **THEN** the members listing SHALL still succeed, returning user ids and
  roles without email/avatar

#### Scenario: Non-member is denied
- **WHEN** a user with no role on the workspace calls the members listing
- **THEN** the request SHALL be rejected with an authorization error

### Requirement: Change a member's role
The system SHALL expose
`PATCH /api/v1/workspaces/{workspace_id}/members/{user_id}` accepting a role.
Only a workspace `owner` SHALL change roles.

#### Scenario: Owner changes a role
- **WHEN** an owner sets a member's role to `commenter`
- **THEN** the member's workspace role SHALL become `commenter`

#### Scenario: Non-owner cannot change roles
- **WHEN** an `editor` attempts to change a member's role
- **THEN** the request SHALL be rejected with an authorization error

### Requirement: Remove a member
The system SHALL expose
`DELETE /api/v1/workspaces/{workspace_id}/members/{user_id}`. Only a workspace
`owner` SHALL remove members. Removal SHALL delete the workspace membership;
document-level grants are unaffected.

#### Scenario: Owner removes a member
- **WHEN** an owner removes a member
- **THEN** the user SHALL no longer hold a workspace role

#### Scenario: Non-owner cannot remove
- **WHEN** a `commenter` attempts to remove a member
- **THEN** the request SHALL be rejected with an authorization error

### Requirement: Last-owner protection
The system SHALL reject any role change or removal that would leave the
workspace with zero owners.

#### Scenario: Demoting the last owner is rejected
- **WHEN** the only owner attempts to change their own role to `editor`
- **THEN** the request SHALL be rejected with a conflict error and the role
  SHALL be unchanged

#### Scenario: Removing the last owner is rejected
- **WHEN** the only owner attempts to remove themselves
- **THEN** the request SHALL be rejected with a conflict error and the
  membership SHALL remain

#### Scenario: Demoting one of several owners succeeds
- **WHEN** a workspace has two owners and one is demoted to `editor`
- **THEN** the change SHALL succeed
