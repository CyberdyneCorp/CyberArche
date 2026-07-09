# ai-agent Specification

## ADDED Requirements
### Requirement: Answers surface their tool calls
An agent answer SHALL report the tool calls made while producing it. Each
reported call SHALL include the tool name, its kind (built-in, document-editing,
or external MCP — with the connector identified for MCP tools), the arguments it
was called with, its result, and whether it succeeded. The chat SHALL present
these calls per answer and let the user expand a call to see its arguments and
result.

#### Scenario: A tool call is reported with the answer
- **WHEN** the agent calls a tool while answering
- **THEN** the answer SHALL include that call's name, kind, arguments, and result

#### Scenario: External MCP calls are identified as such
- **WHEN** the agent calls an external MCP tool
- **THEN** the reported call SHALL be marked as an MCP call and name its connector

#### Scenario: A failed tool call is flagged
- **WHEN** a tool call returns an error
- **THEN** the reported call SHALL be marked as unsuccessful
