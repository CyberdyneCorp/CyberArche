# ai-agent Specification

## ADDED Requirements

### Requirement: Inline text transformation

The system SHALL let a member transform a selected span of text in place via the
agent, for the actions rewrite, shorten, expand, fix (grammar/spelling), and
translate (to a target language). The transformation SHALL be a single LLM call
returning only the transformed text; it SHALL NOT edit the document itself — the
member chooses whether to apply the result. It SHALL require view access to the
document and enforce the caller's tenant scope.

#### Scenario: Rewrite a selection

- **GIVEN** a member viewing a document
- **WHEN** they select text and choose an inline AI action
- **THEN** the system SHALL return the transformed text for that action
- **AND** SHALL NOT modify the document until the member applies the result

#### Scenario: Access required

- **WHEN** a caller without view access requests a transformation
- **THEN** the system SHALL refuse the request
