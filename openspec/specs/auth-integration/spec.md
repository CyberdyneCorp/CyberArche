# auth-integration Specification

## Purpose

CyberdyneAuth as the identity provider: SSO, JWKS-verified JWTs, claims-only tenant scoping, IAM authorization, and service-to-service tokens.
## Requirements
### Requirement: CyberdyneAuth SSO
The system SHALL authenticate users via CyberdyneAuth using OIDC/OAuth2
authorization-code with PKCE, obtaining tokens and identity from the auth
service rather than storing passwords locally.

#### Scenario: Sign in via SSO
- **WHEN** an unauthenticated user starts sign-in
- **THEN** the system SHALL redirect through CyberdyneAuth's authorization
  endpoint and establish a session on successful callback

### Requirement: JWT verification via JWKS
The backend SHALL verify access tokens as JWTs using CyberdyneAuth's published
JWKS (`/.well-known/jwks.json`), and MAY use token introspection
(`/api/v1/auth/introspect`) for opaque or service tokens.

#### Scenario: Reject invalid token
- **WHEN** a request presents a token with an invalid signature or that is expired
- **THEN** the backend SHALL reject the request with 401 before any use case runs

#### Scenario: Accept valid token
- **WHEN** a request presents a valid, unexpired token
- **THEN** the backend SHALL resolve the caller identity from its claims

### Requirement: Tenant and identity from claims
The caller's user identity and tenant/organization SHALL be derived only from
verified token claims (and `/api/v1/users/me` where needed), never from request
path or body.

#### Scenario: Tenant not spoofable
- **WHEN** a request body specifies a different tenant than the token's claim
- **THEN** the system SHALL use the token's tenant and ignore the body value

### Requirement: IAM-driven authorization
The system SHALL honor CyberdyneAuth IAM policies/groups/roles when evaluating
whether a caller may perform an action, and SHALL treat admin access per the auth
service's model.

#### Scenario: Permission evaluation
- **WHEN** the system must decide if a caller may perform a protected action
- **THEN** it SHALL evaluate the caller's resolved IAM assignments and allow or
  deny accordingly

### Requirement: Service-to-service authentication
Background workers and inter-service calls SHALL authenticate using the OAuth2
client-credentials grant against CyberdyneAuth.

#### Scenario: Worker obtains a service token
- **WHEN** a worker needs to call a protected service
- **THEN** it SHALL obtain a client-credentials token and present it as a Bearer
  token

### Requirement: Personal API keys
The system SHALL let an authenticated user create named personal API keys,
list them (identified by a non-secret prefix), and revoke them. The full key
secret SHALL be shown exactly once, at creation, and SHALL be stored only as
a cryptographic hash.

#### Scenario: Create and show once
- **WHEN** a user creates an API key with a name
- **THEN** the system SHALL return the full secret exactly once
- **AND** subsequent listings SHALL expose only the name, prefix, creation
  time, and last-used time

#### Scenario: Secrets are hashed at rest
- **WHEN** an API key is persisted
- **THEN** the stored record SHALL contain a hash of the secret, never the
  secret itself

### Requirement: API keys authenticate as their owner
A valid API key presented as a Bearer credential SHALL authenticate the
request as the key's owning user, with exactly that user's tenant and
permissions, on every inbound surface (HTTP, realtime, MCP).

#### Scenario: MCP client connects with an API key
- **WHEN** an external MCP client presents a valid API key
- **THEN** tool calls SHALL execute with the owner's identity and be subject
  to the owner's permissions

#### Scenario: Key never escalates
- **WHEN** a request authenticates with an API key
- **THEN** it SHALL be denied anything the owning user could not do

### Requirement: API key lifecycle
Revoked or expired API keys SHALL be rejected immediately, and the system
SHALL record when each key was last used.

#### Scenario: Revoked key is rejected
- **WHEN** a request presents a key that has been revoked
- **THEN** the system SHALL reject it with an authentication error

#### Scenario: Expired key is rejected
- **WHEN** a request presents a key past its expiry
- **THEN** the system SHALL reject it with an authentication error

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

