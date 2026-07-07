# ai-agent Specification

## ADDED Requirements

### Requirement: Provider-agnostic LLM access
The AI agent SHALL access language models through an `LLMPort` abstraction so the
model provider (Anthropic, OpenAI, local) is selectable by configuration without
changing application or domain code.

#### Scenario: Switch providers by config
- **WHEN** the configured LLM provider is changed
- **THEN** the agent SHALL use the new provider without code changes to use cases

### Requirement: Document-scoped agent
Every document SHALL have an AI agent whose default context is that document, its
block tree, and (when authorized) the workspace's RAG knowledge.

#### Scenario: Answer grounded in the document
- **WHEN** a user asks the agent a question about the current document
- **THEN** the agent SHALL answer using the document content
- **AND** SHALL cite the blocks or sources it used

### Requirement: Summarize and draft
The agent SHALL summarize a document or selection and SHALL draft or rewrite
content on request, returning results as blocks that can be inserted.

#### Scenario: Summarize a document
- **WHEN** a user requests a summary
- **THEN** the agent SHALL produce a summary the user can insert as blocks

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
