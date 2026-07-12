# google-workspace-connector Specification

## Purpose
TBD - created by archiving change google-workspace-connector. Update Purpose after archive.
## Requirements
### Requirement: Connect a Google account

The system SHALL let a user connect a personal Google account to a workspace via
a Google OAuth2 authorization-code flow, requesting only the scopes needed for
the tool groups the user consents to, and SHALL store the resulting access and
refresh tokens encrypted at rest per `user + workspace`. Access tokens SHALL be
refreshed automatically using the stored refresh token. The system SHALL NOT
return stored tokens in plaintext.

Google Workspace is the only first-party SaaS connector; all other SaaS
integrations (e.g. Slack, Jira) are served by the external-MCP connectors and are
out of scope for this capability.

#### Scenario: Complete the OAuth flow

- **GIVEN** a user starts the connect flow for a workspace and grants the
  requested scopes
- **WHEN** Google redirects back with a valid authorization code and matching
  `state`
- **THEN** the system SHALL exchange the code for access and refresh tokens
- **AND** SHALL store both tokens encrypted at rest with the granted scopes and a
  `connected` status
- **AND** SHALL make the corresponding Google tools available to that user

#### Scenario: Minimal scopes per tool group

- **GIVEN** a user enables only the Calendar tool group
- **WHEN** the consent URL is built
- **THEN** the system SHALL request only Calendar scopes
- **AND** SHALL NOT request Gmail or Drive scopes

#### Scenario: Tokens are never revealed

- **WHEN** a user or client views the Google connection
- **THEN** the system SHALL show metadata (status, granted scopes, connected
  email) but SHALL NOT return the stored access or refresh tokens in plaintext

#### Scenario: Automatic token refresh

- **GIVEN** a connected user whose access token has expired
- **WHEN** a Google tool is invoked
- **THEN** the system SHALL refresh the access token using the stored refresh
  token and re-encrypt the updated tokens
- **AND** SHALL complete the tool call without user intervention

#### Scenario: Refresh failure requires reconnect

- **GIVEN** a connected user whose refresh token has been revoked at Google
- **WHEN** a Google tool is invoked and the refresh fails
- **THEN** the system SHALL set the connection status to `needs_reconnect`
- **AND** SHALL return a clear error asking the user to reconnect Google

#### Scenario: Reject a callback with an invalid state

- **WHEN** an OAuth callback arrives with a missing or mismatched `state`
- **THEN** the system SHALL reject it and SHALL NOT store any tokens

### Requirement: Gmail tools

The system SHALL provide agent tools to search and read the connected user's
Gmail, and to compose a draft message or reply. The system SHALL require an
explicit user action before any mail is sent; the agent SHALL NOT send mail
autonomously.

#### Scenario: Search and read mail

- **GIVEN** a user connected with the `gmail.readonly` scope
- **WHEN** the agent runs a Gmail search or reads a message on that user's behalf
- **THEN** the system SHALL return matching messages the user can access

#### Scenario: Compose produces a draft, not a send

- **GIVEN** a user connected with the `gmail.compose` scope
- **WHEN** the agent composes a reply
- **THEN** the system SHALL create a draft (or present it for review)
- **AND** SHALL NOT send the message until the user explicitly confirms sending

#### Scenario: Missing scope blocks the tool

- **GIVEN** a user connected without the Gmail scope
- **WHEN** a Gmail tool is invoked
- **THEN** the system SHALL NOT call Google
- **AND** SHALL return an error asking the user to grant Gmail permission

### Requirement: Calendar tools and scheduling

The system SHALL provide agent tools to list Calendar events, find free/busy
times across a window, and create events. The system SHALL require an explicit
user action before an event is created; the agent SHALL NOT create events
autonomously.

#### Scenario: Find free/busy times

- **GIVEN** a user connected with the Calendar scope
- **WHEN** the agent requests free/busy for a time window
- **THEN** the system SHALL return the user's busy periods and/or open slots for
  that window

#### Scenario: Creating an event requires explicit action

- **GIVEN** a proposed meeting time chosen by the user
- **WHEN** the agent prepares to create the event
- **THEN** the system SHALL create the event only after the user explicitly
  confirms it
- **AND** SHALL NOT create the event autonomously

### Requirement: Docs and Drive import

The system SHALL provide agent tools to search and read the connected user's
Google Drive files and Docs, and to import a Google Doc into a CyberArche
document as blocks. Imported and read results SHALL be insertable into the
document and citable.

#### Scenario: Search and read Drive/Docs

- **GIVEN** a user connected with the Drive/Docs read scopes
- **WHEN** the agent searches Drive or reads a Doc on that user's behalf
- **THEN** the system SHALL return matching files/content the user can access

#### Scenario: Import a Doc as blocks

- **GIVEN** a connected user and a Google Doc id
- **WHEN** the agent imports the Doc
- **THEN** the system SHALL map the Doc's structure to CyberArche blocks
  (headings, text, lists, tables, code)
- **AND** the resulting blocks SHALL be insertable into the document and carry a
  reference to the source Doc

### Requirement: Per-user isolation of Google data

A Google connection SHALL be personal to the user who created it. The system
SHALL use a connection only for that user's own requests and SHALL never expose
one user's Google data to another user. All storage and queries SHALL respect
tenant isolation.

#### Scenario: A user cannot use another user's connection

- **GIVEN** user A has a connected Google account and user B does not
- **WHEN** user B invokes a Google tool in the same workspace
- **THEN** the system SHALL NOT use user A's connection
- **AND** SHALL treat user B as not connected

#### Scenario: Tenant isolation

- **GIVEN** a Google connection stored for one tenant
- **WHEN** a request is made under a different tenant
- **THEN** the system SHALL NOT return or use that connection, enforced by
  row-level security on `tenant_id`

#### Scenario: Disconnect revokes access

- **GIVEN** a connected user
- **WHEN** the user disconnects Google from settings
- **THEN** the system SHALL revoke the tokens at Google and remove the stored
  tokens
- **AND** subsequent Google tool calls SHALL fail as not connected until the user
  reconnects

