# ai-agent Specification

## Purpose

The per-document AI assistant: grounded answers, summarize/draft, file ingestion, tool use via MCP, editing as a CRDT peer, with audited runs over a provider-agnostic LLM.
## Requirements
### Requirement: Provider-agnostic LLM access
The AI agent SHALL access language models through an `LLMPort` abstraction so the
model provider (Anthropic, OpenAI, local) is selectable by configuration without
changing application or domain code.

#### Scenario: Switch providers by config
- **WHEN** the configured LLM provider is changed
- **THEN** the agent SHALL use the new provider without code changes to use cases

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

### Requirement: Summarize and draft
The agent SHALL summarize a document or a selection of blocks, and SHALL draft
or rewrite content on request, returning results as blocks that can be inserted.
When a selection is given, the summary SHALL be scoped to the selected blocks.

#### Scenario: Summarize a document
- **WHEN** a user requests a summary with no selection
- **THEN** the agent SHALL produce a summary of the whole document the user can
  insert as blocks

#### Scenario: Summarize a selection
- **WHEN** a user requests a summary of specific block ids
- **THEN** the agent SHALL scope the summary to those blocks

#### Scenario: Rewrite a selection
- **WHEN** a user selects blocks and requests a rewrite with an instruction
- **THEN** the agent SHALL return revised blocks for that selection

### Requirement: Agent edits as a CRDT peer
When the agent modifies a document, it SHALL apply changes through the same CRDT
channel as human editors, so agent edits are collaborative, attributable, and
appear live to other participants.

#### Scenario: Live agent edit
- **WHEN** the agent applies an edit to an open document
- **THEN** connected participants SHALL see the edit appear live attributed to
  the agent
- **AND** the edit SHALL merge conflict-free with concurrent human edits

### Requirement: File ingestion into documents
The agent SHALL ingest uploaded PDF, CSV, and Excel files: extracting text and
structure into blocks, converting tabular data (CSV/Excel) into `table` blocks,
and submitting content to RAG for retrieval.

#### Scenario: Ingest a PDF
- **WHEN** a user uploads a PDF and asks the agent to ingest it
- **THEN** the agent SHALL extract its content into document blocks
- **AND** SHALL submit the document to the workspace's RAG project

#### Scenario: Ingest a spreadsheet as a table
- **WHEN** a user uploads a CSV or Excel file for ingestion
- **THEN** the agent SHALL create a `table` block matching the sheet's rows and
  columns

### Requirement: Tool use via MCP
The agent SHALL be able to call tools exposed by the CyberArche MCP server and by
any attached external MCP servers, subject to the caller's permissions.

#### Scenario: Retrieve another document via a tool
- **WHEN** the agent needs content from another document the user may access
- **THEN** the agent SHALL call a document tool and receive only content the
  caller is authorized to read

### Requirement: Agent run auditing
The system SHALL record each agent run (prompt, tools invoked, documents touched,
model used, outcome) for review.

#### Scenario: Inspect an agent run
- **WHEN** a user opens the history of agent activity on a document
- **THEN** the system SHALL show each run with its prompt, tools, and result

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
An agent answer that did not itself modify the document SHALL be accompanied by
blocks derived from it, so the user can insert the answer without retyping it.
When the agent already applied its change to the document during the run (via an
editing tool), the answer SHALL NOT offer the same content for manual insertion,
so it is not added twice. Blocks the agent inserts SHALL be normalized so a
source-based block (code, latex, mermaid) is never left empty when its content
was provided under a different field.

#### Scenario: Insert a conversational answer
- **WHEN** the agent answers a question without editing the document
- **THEN** the response SHALL include blocks representing the answer
- **AND** the user SHALL be able to insert them into the document

#### Scenario: No duplicate insert after a live edit
- **WHEN** the agent applies an edit to the document during its run
- **THEN** the answer SHALL NOT carry insertable blocks for that content

#### Scenario: An agent-inserted source block is never empty
- **WHEN** the agent inserts a mermaid, latex, or code block with the content
  under a field other than `source`
- **THEN** the inserted block SHALL still render that content, not a placeholder

### Requirement: Agent generates images
When image generation is configured, the agent SHALL offer a tool that creates
an image from a text prompt, stores it, and inserts an image block into the open
document as a CRDT peer (attributed like other agent edits). The caller SHALL
need edit permission on the document. When image generation is not configured,
the tool SHALL report that it is unavailable rather than failing the run.

#### Scenario: Agent creates and inserts an image
- **GIVEN** image generation is configured and the caller may edit the document
- **WHEN** the agent calls the image tool with a prompt
- **THEN** an image SHALL be generated, stored, and inserted as an image block in
  the open document

#### Scenario: Image generation not configured
- **WHEN** the agent calls the image tool but no image provider is configured
- **THEN** the tool SHALL report that image generation is unavailable
- **AND** the run SHALL continue without error

