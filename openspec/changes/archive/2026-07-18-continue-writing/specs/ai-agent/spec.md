# ai-agent Specification

## ADDED Requirements

### Requirement: AI continuation suggestions

The system SHALL offer AI continuation suggestions while a member writes. Given
the text preceding the caret, it SHALL return a short natural continuation as a
single LLM call, returning only the suggested text and never editing the
document itself — the member accepts or dismisses the suggestion. It SHALL
require view access to the document and enforce the caller's tenant scope, and
SHALL return nothing when there is no preceding text to continue.

#### Scenario: Suggest a continuation

- **GIVEN** a member writing in a document
- **WHEN** they pause with text before the caret
- **THEN** the system SHALL return a short continuation of that text
- **AND** SHALL NOT modify the document until the member accepts it

#### Scenario: Nothing to continue

- **WHEN** a continuation is requested with no preceding text
- **THEN** the system SHALL return no suggestion
