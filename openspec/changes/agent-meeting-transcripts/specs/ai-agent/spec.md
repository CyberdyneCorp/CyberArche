# ai-agent Specification

## ADDED Requirements

### Requirement: Agent reads the caller's meeting transcripts

When a meeting-transcript provider (Cyberflies) is configured, the agent SHALL
offer tools to list the caller's meeting recordings, fetch a recording's
transcript and summary, and answer natural-language questions across the
caller's meetings. These tools SHALL be read-only: they return information for
the agent to use (e.g. to insert as blocks) and SHALL NOT themselves modify the
document.

#### Scenario: Insert a meeting transcript

- **GIVEN** the caller has a recording in Cyberflies
- **WHEN** the caller asks the agent to add that meeting's transcript to the
  document
- **THEN** the agent SHALL retrieve the transcript and summary for that recording
- **AND** insert the content into the open document

#### Scenario: Answer from meetings

- **WHEN** the caller asks the agent a question about their meetings
- **THEN** the agent MAY query the meeting provider across the caller's meetings
  and answer from the result

### Requirement: Meeting access is delegated to the caller's identity

The agent SHALL access the meeting provider using the caller's own access token,
forwarded as a delegation credential only on the interactive request path and
only to the single configured provider URL. The system SHALL NOT use a service
token or any other user's identity for meeting access, so the provider enforces
that the agent reads only what the caller is entitled to. The caller's token
SHALL NOT be written to logs or audit records.

#### Scenario: Only the caller's meetings are reachable

- **WHEN** the agent calls the meeting provider on the caller's behalf
- **THEN** it SHALL authenticate as the caller
- **AND** SHALL only be able to read recordings the caller owns or that are
  shared with the caller by the provider

#### Scenario: Tools are absent without a caller token or provider

- **WHEN** the meeting provider is not configured, or the request carries no
  caller access token
- **THEN** the meeting tools SHALL NOT be offered to the model
