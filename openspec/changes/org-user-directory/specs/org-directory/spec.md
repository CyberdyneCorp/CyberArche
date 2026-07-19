# org-directory Specification (delta)

## ADDED Requirements

### Requirement: Organization user listing
The system SHALL expose `GET /api/v1/org/users` returning the users of the
caller's organization as provided by the CyberdyneAuth directory. Each entry
SHALL include the user id, email, avatar URL (nullable), and active flag. The
organization SHALL be resolved exclusively from the caller's verified token
claims; the endpoint SHALL NOT accept an organization identifier from the
request. The endpoint SHALL support `search` (case-insensitive substring on
email), and `page`/`page_size` pagination, returning the total count.

#### Scenario: Member lists their organization's users
- **WHEN** an authenticated user whose token carries an `org_id` claim calls
  `GET /api/v1/org/users`
- **THEN** the response SHALL contain the users of that organization with id,
  email, avatar URL, and active flag, plus `total`, `page`, and `page_size`

#### Scenario: Search by email
- **WHEN** the caller passes `search=ada`
- **THEN** only users whose email contains `ada` (case-insensitive) SHALL be
  returned

#### Scenario: Personal tenant has no directory
- **WHEN** a user whose token has no organization claim (personal tenant)
  calls the endpoint
- **THEN** the response SHALL be an empty page with `total` 0, not an error

#### Scenario: Organization cannot be chosen by the caller
- **WHEN** a caller supplies any organization identifier in the path, query,
  or body
- **THEN** it SHALL have no effect; results SHALL always be scoped to the
  organization in the caller's verified claims

### Requirement: Directory access uses the service identity
The backend SHALL call CyberdyneAuth's org-members endpoint using its own
client-credentials service token carrying the `directory:read` grant. The
backend SHALL NOT forward the end user's bearer token to the directory and
SHALL NOT persist directory results.

#### Scenario: Service token used
- **WHEN** the backend queries the CyberdyneAuth directory
- **THEN** the request SHALL authenticate with the service token, not the
  caller's token

### Requirement: Directory unavailability degrades gracefully
The system SHALL return `503` with a typed error body from
`GET /api/v1/org/users` when the CyberdyneAuth directory is unreachable,
errors, or rejects the service token, so clients can fall back to raw-id
entry. Directory failures SHALL NOT break membership listing or any sharing
operation.

#### Scenario: Directory outage
- **WHEN** CyberdyneAuth is unreachable and a user calls
  `GET /api/v1/org/users`
- **THEN** the response SHALL be `503` with a machine-readable error code

#### Scenario: Sharing still works during an outage
- **WHEN** the directory is unavailable
- **THEN** inviting by raw user id and listing workspace members SHALL still
  succeed
