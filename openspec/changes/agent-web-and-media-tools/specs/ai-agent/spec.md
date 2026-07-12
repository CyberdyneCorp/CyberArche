# ai-agent Specification

## ADDED Requirements

### Requirement: Agent web search

The system SHALL provide the document agent a web search tool that queries the
DAO backend and returns ranked results (title, url, snippet) the agent can cite
and insert into the document. The tool SHALL authenticate by forwarding the
caller's own CyberdyneAuth bearer token to the DAO backend, so results are
scoped to what that caller may access; the system SHALL NOT use a delegation or
service token for it. The tool SHALL be available only when the DAO base URL is
configured AND a caller access token is present, and SHALL otherwise be reported
gracefully as unavailable without failing the agent run.

#### Scenario: Search and cite

- **GIVEN** the DAO base URL is configured and the caller presented an access token
- **WHEN** the user asks the agent to research a topic on the web
- **THEN** the agent SHALL call web search, forwarding the caller's bearer token
- **AND** SHALL receive ranked results (title, url, snippet) it can cite and
  insert as blocks

#### Scenario: Results scoped to the caller

- **GIVEN** the forwarded token is the caller's own CyberdyneAuth bearer
- **WHEN** the agent performs a web search
- **THEN** the DAO backend SHALL scope the results to what that caller may access
- **AND** the system SHALL NOT send any service token or shared secret in its place

#### Scenario: Tool unavailable when unconfigured or unauthenticated

- **GIVEN** the DAO base URL is not configured OR no caller access token is present
- **WHEN** the agent is assembled for a run
- **THEN** the web search tool SHALL NOT be offered
- **AND** any invocation SHALL be reported gracefully as unavailable without
  aborting the run

### Requirement: Agent YouTube tools

The system SHALL provide the document agent YouTube tools backed by the DAO
backend: a transcript tool that fetches a video's transcript (the video given as
a URL or an 11-character id, with an optional language) and a playlist tool that
lists a playlist's videos. Both SHALL authenticate by forwarding the caller's
own CyberdyneAuth bearer token to the DAO backend, and SHALL be available only
when the DAO base URL is configured AND a caller access token is present,
otherwise reported gracefully as unavailable. A fetched transcript SHALL be
usable by the agent either to summarize into the open document or to ingest into
the workspace RAG knowledge base through the existing ingestion path.

#### Scenario: Fetch and summarize a transcript

- **GIVEN** the YouTube tools are configured and the caller presented an access token
- **WHEN** the user asks the agent to summarize a video
- **THEN** the agent SHALL fetch the transcript, forwarding the caller's bearer token
- **AND** SHALL summarize it into the document as blocks the user can insert

#### Scenario: Ingest a transcript into the knowledge base

- **GIVEN** a transcript has been fetched
- **WHEN** the user asks the agent to add the video to the workspace knowledge base
- **THEN** the agent SHALL ingest the transcript through the existing RAG
  ingestion path, enforcing the caller's ingestion permission and workspace scope

#### Scenario: List a playlist and unavailable when unconfigured

- **GIVEN** the DAO base URL is not configured OR no caller access token is present
- **WHEN** the agent is assembled for a run
- **THEN** the YouTube transcript and playlist tools SHALL NOT be offered
- **AND** any invocation SHALL be reported gracefully as unavailable without
  aborting the run
