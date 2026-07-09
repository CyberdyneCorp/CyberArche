# ai-agent Specification

## MODIFIED Requirements

### Requirement: Every answer yields insertable blocks
An agent answer SHALL be accompanied by blocks derived from it, so the user can
insert the answer into the document without retyping it. The blocks SHALL be
typed to match the answer's content: fenced code SHALL become `code` blocks,
fenced Mermaid SHALL become `mermaid` blocks, display math SHALL become `latex`
blocks, and prose SHALL become paragraph blocks. Inserting an answer SHALL apply
the blocks to the open document immediately, whether or not the realtime
connection is currently established.

#### Scenario: Insert a conversational answer
- **WHEN** the agent answers a question
- **THEN** the response SHALL include blocks representing the answer
- **AND** the user SHALL be able to insert them into the document

#### Scenario: Math becomes a latex block
- **WHEN** the agent's answer contains display math (`$$…$$` or `\[…\]`)
- **THEN** that math SHALL be a `latex` block preserving the source

#### Scenario: A diagram becomes a mermaid block
- **WHEN** the agent's answer contains a fenced ```mermaid block
- **THEN** it SHALL become a `mermaid` block with that source

#### Scenario: Code becomes a code block
- **WHEN** the agent's answer contains a fenced code block with a language
- **THEN** it SHALL become a `code` block with that language and source

#### Scenario: Insert works while offline
- **WHEN** the user inserts an answer while the realtime connection is down
- **THEN** the blocks SHALL appear in the open document immediately
- **AND** SHALL sync to the server when the connection is restored
