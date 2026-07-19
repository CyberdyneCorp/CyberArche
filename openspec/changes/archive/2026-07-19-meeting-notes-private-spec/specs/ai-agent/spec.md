# ai-agent Specification

## MODIFIED Requirements

### Requirement: Meeting transcript to structured document

The system SHALL let a member turn one of their meeting recordings into a new
structured document. It SHALL fetch the recording's transcript using the
member's delegated credential, use the LLM to structure it into a summary, key
points, decisions, and action items, create a document in the target workspace
titled from the recording, and populate it with the structured content as
editable blocks. The document SHALL be created as a private document of the
workspace — not within a teamspace — so it appears in the member's Private
section. Creating the document SHALL require edit access to the workspace, and
the recording SHALL be read using the member's own access token so the provider
enforces per-user access. When meeting transcripts are not configured, or the
caller is not signed in with a delegable token, the system SHALL return a clear
error and SHALL NOT create a document.

#### Scenario: Generate a document from a recording

- **GIVEN** a signed-in member with a meeting recording and edit access to a
  workspace
- **WHEN** they generate meeting notes from that recording
- **THEN** the system SHALL create a document containing the structured summary,
  decisions, and action items
- **AND** SHALL return the new document so it can be opened

#### Scenario: Generated document is private

- **WHEN** a member generates meeting notes from a recording
- **THEN** the created document SHALL belong to the workspace without a teamspace
  (a private document), appearing in the member's Private section

#### Scenario: Meetings not configured

- **WHEN** meeting transcripts are not configured on the deployment
- **THEN** the system SHALL return a clear error and SHALL NOT create a document
