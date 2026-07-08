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
