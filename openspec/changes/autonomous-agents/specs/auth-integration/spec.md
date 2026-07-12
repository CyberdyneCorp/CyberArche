# auth-integration Specification

## ADDED Requirements

### Requirement: CyberArche service token for background work
For background work that has no live user token, CyberArche SHALL authenticate
as itself by obtaining an OAuth2 client-credentials token from CyberdyneAuth at
`POST /api/v1/auth/oauth2/token` using `grant_type=client_credentials`,
`client_secret_basic` client authentication, and the scopes required for the
work (e.g. `cyberrag:query interpreter:execute`), optionally specifying an
`audience`. The resulting service token has `type=service` and subject
`client:<id>` and carries its granted scopes. CyberArche SHALL cache the token
in memory and refresh it before it expires, and SHALL use it only as a transport
credential to sibling backends — never as the end-user authority for a run.
Interactive requests SHALL continue to forward the caller's own user bearer
token and SHALL NOT mint a service token.

#### Scenario: Acquire a service token for a background run
- **GIVEN** a background run with no live user token
- **WHEN** CyberArche needs to call a protected sibling backend
- **THEN** it SHALL request a client-credentials token with the required scopes
- **AND** SHALL present that token as a Bearer credential to the sibling backend

#### Scenario: Cache and refresh the service token
- **GIVEN** a previously acquired, still-valid service token
- **WHEN** another background call needs a service token before it expires
- **THEN** CyberArche SHALL reuse the cached token
- **AND** SHALL request a new token only once the cached one is near or past
  expiry

#### Scenario: Service token is transport only, not authority
- **GIVEN** a service token whose subject is `client:<id>` and which carries
  service scopes
- **WHEN** a background run authorizes what it may read or change
- **THEN** the run's authority SHALL come from the stored task owner's identity
  and permissions
- **AND** the service token SHALL grant no end-user access on its own

#### Scenario: Interactive requests do not use a service token
- **GIVEN** an interactive request carrying a valid user bearer token
- **WHEN** CyberArche calls a sibling backend on that request's behalf
- **THEN** it SHALL forward the caller's user bearer token
- **AND** SHALL NOT substitute a client-credentials service token
