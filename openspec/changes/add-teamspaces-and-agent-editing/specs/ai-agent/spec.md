# ai-agent Specification

## ADDED Requirements

### Requirement: Agent edits the open document through tools
The agent SHALL be able to insert, update, and delete blocks in the document
it is scoped to, using tools bound to that document, and SHALL apply every
change through the CRDT so collaborators see it live.

#### Scenario: Add text to an existing block
- **WHEN** a user asks the agent to add text to a block of the open document
- **THEN** the agent SHALL update that block through the CRDT
- **AND** the change SHALL appear live to connected participants

#### Scenario: Insert a new block
- **WHEN** the agent is asked to add a section
- **THEN** it SHALL insert the block(s) through the CRDT, attributed to the agent

#### Scenario: Delete a block
- **WHEN** the agent is asked to remove a block it can identify
- **THEN** the block SHALL be removed from the document

#### Scenario: Editing requires edit permission
- **WHEN** a caller with view-only permission asks the agent to change the document
- **THEN** the edit SHALL be denied and no change SHALL be applied

#### Scenario: Editing tools are scoped to the open document
- **WHEN** the agent calls an editing tool
- **THEN** it SHALL affect only the document the agent is scoped to

### Requirement: Every answer yields insertable blocks
An agent answer SHALL be accompanied by blocks derived from it, so the user can
insert the answer into the document without retyping it.

#### Scenario: Insert a conversational answer
- **WHEN** the agent answers a question
- **THEN** the response SHALL include blocks representing the answer
- **AND** the user SHALL be able to insert them into the document

## MODIFIED Requirements

### Requirement: Document-scoped agent
Every document SHALL have an AI agent whose default context is that document,
its block tree, and (when authorized) the workspace's RAG knowledge. The agent
SHALL be told the identifiers of the document's blocks so it can reference them
when editing.

#### Scenario: Answer grounded in the document
- **WHEN** a user asks the agent a question about the current document
- **THEN** the agent SHALL answer using the document content
- **AND** SHALL cite the blocks or sources it used

#### Scenario: Agent knows the open document's identity
- **WHEN** the agent is invoked on a document
- **THEN** its context SHALL identify that document and its blocks
- **AND** the agent SHALL NOT need to look the document up by title
