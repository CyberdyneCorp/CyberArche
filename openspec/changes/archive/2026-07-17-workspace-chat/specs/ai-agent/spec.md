# ai-agent Specification

## ADDED Requirements

### Requirement: Workspace-wide chat

The system SHALL provide a workspace-scoped conversational agent that answers
questions grounded in the workspace's documents, independent of any open
document. It SHALL ground answers using the workspace's RAG knowledge base and
full-text search over the workspace's documents, apply the workspace's persona
and instructions, and consider recent conversation history. It SHALL be
read-only — it SHALL NOT create or modify documents — and SHALL enforce
workspace membership and return only content the caller may access.

#### Scenario: Answer grounded in the workspace

- **GIVEN** a member of a workspace with documents
- **WHEN** the member asks the workspace chat a question
- **THEN** the system SHALL return an answer drawn from the workspace's RAG
  knowledge and/or matching documents
- **AND** SHALL include the source documents it drew on

#### Scenario: Membership required

- **WHEN** a caller who is not a member of the workspace uses the chat
- **THEN** the system SHALL refuse the request

#### Scenario: Read-only

- **WHEN** the workspace chat answers
- **THEN** it SHALL NOT create, edit, or delete any document
