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

#### Scenario: Edit a table block's cells
- **GIVEN** the open document contains a `table` block
- **WHEN** the agent is asked to change the table's contents
- **THEN** the agent's context SHALL show the table's current header and rows
- **AND** the agent SHALL rewrite the cells through a table-editing tool
  (updating a text field SHALL NOT be treated as editing the table)

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
was provided under a different field. When the agent inserts a `paragraph` whose
text carries block-level markdown (a `#`/`##`/`###` heading, a fenced code
block, display math, a list item, or a blockquote), that paragraph SHALL be
split into the corresponding typed blocks, because the editor renders
block-level markdown only as its own block and would otherwise show the raw
`## …` / ```` ``` ```` source as literal text.

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

#### Scenario: A markdown blob paragraph is split into typed blocks
- **WHEN** the agent inserts a `paragraph` whose text contains block-level
  markdown such as a `## heading` followed by a fenced code block
- **THEN** the insertion SHALL produce a `heading` block and a `code` block
- **AND** the document SHALL NOT contain a paragraph rendering `## …` or the
  code fence as literal text

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

### Requirement: Agent runs Python
When code execution is configured, the agent SHALL offer a tool that runs Python
to compute, analyze data, run simulations, or plot. Figures the code produces
SHALL be stored and inserted into the open document as image blocks (a CRDT peer
edit), and the standard output, result value, and any error SHALL be returned to
the agent so it can explain them. The caller SHALL need edit permission on the
document. When code execution is not configured, the tool SHALL report it is
unavailable rather than failing the run.

#### Scenario: Agent plots and inserts a figure
- **GIVEN** code execution is configured and the caller may edit the document
- **WHEN** the agent runs Python that creates a plot
- **THEN** the figure SHALL be inserted into the document as an image block
- **AND** the run's stdout and result SHALL be available to the agent

#### Scenario: Code execution not configured
- **WHEN** the agent calls the Python tool but no interpreter is configured
- **THEN** the tool SHALL report that code execution is unavailable
- **AND** the run SHALL continue without error

### Requirement: Agent uses recent conversation history
The agent SHALL accept recent conversation turns with a request and take them
into account, so a follow-up instruction that refers to the prior exchange (e.g.
"insert the plot", "run that code") resolves against the conversation rather than
only the document. The amount of history included MAY be bounded.

#### Scenario: A follow-up resolves against the prior turn
- **GIVEN** the user asked the agent to create a plot and got a reply
- **WHEN** the user then says "insert the plot"
- **THEN** the agent SHALL interpret "the plot" as the one from the prior turn

#### Scenario: History is optional
- **WHEN** a request is made with no prior turns
- **THEN** the agent SHALL answer from the document and instruction alone

### Requirement: Agent reads excalidraw scenes

When the agent reads a document containing an `excalidraw` block, it SHALL
include a textual description of the scene (the shapes present, their text
labels, and the connections between them) in the context it reasons over, so it
can answer questions about a diagram the user drew.

#### Scenario: Agent summarizes a drawn diagram

- **GIVEN** a document with an `excalidraw` block containing labelled shapes and
  connectors
- **WHEN** the user asks the agent about the diagram
- **THEN** the agent's document context SHALL describe the shapes, their labels,
  and their connections

### Requirement: Agent creates diagrams

The agent SHALL be able to create a diagram in a document by generating a valid
`.excalidraw` scene and inserting it as an `excalidraw` block. At minimum it
SHALL support generating a mind map from a central topic and its branches.

#### Scenario: Agent creates a mind map

- **WHEN** the user asks the agent to "create a mind map" for a topic
- **THEN** the agent SHALL insert an `excalidraw` block whose scene contains a
  central node and connected branch nodes
- **AND** the block SHALL render the generated diagram

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

### Requirement: Per-request reasoning effort

The chat window SHALL let the user toggle reasoning for a message. When enabled,
the agent SHALL request deeper reasoning from the model; when disabled, it SHALL
request minimal reasoning for a fast, cheap response. The reasoning setting SHALL
apply to that request's model calls, and SHALL be a no-op for models that do not
support reasoning effort (so it never breaks a non-reasoning model).

#### Scenario: Reasoning on requests deeper thinking

- **WHEN** the user sends a message with the reasoning toggle on
- **THEN** the agent SHALL call the model with a higher reasoning effort

#### Scenario: Reasoning off is fast

- **WHEN** the user sends a message with the reasoning toggle off
- **THEN** the agent SHALL call the model with minimal reasoning effort

### Requirement: Forward-compatible token limit

The OpenAI-compatible adapter SHALL cap responses using `max_completion_tokens`
so that reasoning models (GPT-5 family, o-series), which reject the legacy
`max_tokens` field, are supported alongside earlier models.

#### Scenario: A reasoning model is callable

- **WHEN** the configured model is a GPT-5 / o-series model
- **THEN** a completion request SHALL succeed rather than being rejected for an
  unsupported token field

### Requirement: Agent web search

The system SHALL provide the document agent a web search tool that queries the
DAO backend and returns ranked results (title, url, snippet) the agent can cite
and insert into the document. The tool SHALL authenticate by forwarding the
caller's own CyberdyneAuth bearer token to the DAO backend, so results are
scoped to what that caller may access; the system SHALL NOT use a delegation or
service token for it. The tool SHALL be available only when the DAO base URL is
configured AND a caller access token is present, and SHALL otherwise be reported
gracefully as unavailable without failing the agent run.

#### Scenario: Search and cite

- **GIVEN** the DAO base URL is configured and the caller presented an access token
- **WHEN** the user asks the agent to research a topic on the web
- **THEN** the agent SHALL call web search, forwarding the caller's bearer token
- **AND** SHALL receive ranked results (title, url, snippet) it can cite and
  insert as blocks

#### Scenario: Results scoped to the caller

- **GIVEN** the forwarded token is the caller's own CyberdyneAuth bearer
- **WHEN** the agent performs a web search
- **THEN** the DAO backend SHALL scope the results to what that caller may access
- **AND** the system SHALL NOT send any service token or shared secret in its place

#### Scenario: Tool unavailable when unconfigured or unauthenticated

- **GIVEN** the DAO base URL is not configured OR no caller access token is present
- **WHEN** the agent is assembled for a run
- **THEN** the web search tool SHALL NOT be offered
- **AND** any invocation SHALL be reported gracefully as unavailable without
  aborting the run

### Requirement: Agent YouTube tools

The system SHALL provide the document agent YouTube tools backed by the DAO
backend: a transcript tool that fetches a video's transcript (the video given as
a URL or an 11-character id, with an optional language) and a playlist tool that
lists a playlist's videos. Both SHALL authenticate by forwarding the caller's
own CyberdyneAuth bearer token to the DAO backend, and SHALL be available only
when the DAO base URL is configured AND a caller access token is present,
otherwise reported gracefully as unavailable. A fetched transcript SHALL be
usable by the agent either to summarize into the open document or to ingest into
the workspace RAG knowledge base through the existing ingestion path.

#### Scenario: Fetch and summarize a transcript

- **GIVEN** the YouTube tools are configured and the caller presented an access token
- **WHEN** the user asks the agent to summarize a video
- **THEN** the agent SHALL fetch the transcript, forwarding the caller's bearer token
- **AND** SHALL summarize it into the document as blocks the user can insert

#### Scenario: Ingest a transcript into the knowledge base

- **GIVEN** a transcript has been fetched
- **WHEN** the user asks the agent to add the video to the workspace knowledge base
- **THEN** the agent SHALL ingest the transcript through the existing RAG
  ingestion path, enforcing the caller's ingestion permission and workspace scope

#### Scenario: List a playlist and unavailable when unconfigured

- **GIVEN** the DAO base URL is not configured OR no caller access token is present
- **WHEN** the agent is assembled for a run
- **THEN** the YouTube transcript and playlist tools SHALL NOT be offered
- **AND** any invocation SHALL be reported gracefully as unavailable without
  aborting the run

### Requirement: Agent custom instructions

Each workspace SHALL have optional custom instructions that shape the agent's
tone and behavior, and the system SHALL prepend them to the agent's system prompt
on every run in that workspace. The system SHALL additionally support optional
per-user personal instructions layered on top of the workspace instructions for
the calling user only. Only workspace owners or editors SHALL set or clear a
workspace's custom instructions; personal instructions SHALL be readable and
writable only by their author. Custom instructions SHALL be tenant-isolated and
SHALL NOT be visible across tenants.

#### Scenario: Workspace instructions shape the agent

- **GIVEN** a workspace whose custom instructions say to answer in Portuguese and
  always cite sources
- **WHEN** a user asks the workspace's agent a question
- **THEN** the system SHALL prepend those instructions to the agent's system
  prompt for that run
- **AND** the agent SHALL follow them alongside the base document context

#### Scenario: Personal instructions layer on top

- **GIVEN** a user with personal instructions in addition to the workspace's
  custom instructions
- **WHEN** that user runs the agent
- **THEN** the system SHALL inject both the workspace instructions and that user's
  personal instructions
- **AND** SHALL NOT inject that user's personal instructions for any other user

#### Scenario: Only authorized roles edit workspace instructions

- **GIVEN** a caller with viewer-only access to a workspace
- **WHEN** the caller attempts to set the workspace's custom instructions
- **THEN** the system SHALL deny the change
- **AND** SHALL leave the existing instructions unchanged

#### Scenario: Owner or editor sets workspace instructions

- **GIVEN** a caller who is an owner or editor of the workspace
- **WHEN** the caller sets the workspace's custom instructions
- **THEN** the system SHALL store them for that workspace
- **AND** subsequent agent runs in that workspace SHALL use them

### Requirement: Agent persistent memory

The agent SHALL be able to save durable notes to a workspace-scoped memory via a
`remember` tool during a run, and the system SHALL recall relevant memories and
inject them into the agent's context on later runs in that workspace. Injected
memory SHALL be bounded by a token budget so it cannot crowd out document context.
Memory SHALL be tenant- and workspace-isolated and SHALL NOT leak across tenants
or workspaces. Saving a memory SHALL require editor access to the workspace, and
the system SHALL reject notes that contain obvious secrets (tokens, passwords, or
keys). Users SHALL be able to view, edit, and delete memories, subject to
workspace access control.

#### Scenario: Agent remembers a fact and recalls it later

- **GIVEN** a workspace agent in a conversation
- **WHEN** the agent calls `remember` to save "the team ships in Solidity and uses
  Foundry"
- **THEN** the system SHALL persist that note scoped to the workspace and tenant
- **AND** in a later, separate conversation in the same workspace the system SHALL
  inject that memory into the agent's context

#### Scenario: Memory is workspace and tenant scoped

- **GIVEN** a memory saved in workspace A of tenant T1
- **WHEN** the agent runs in workspace B, or in any workspace of a different tenant
  T2
- **THEN** the system SHALL NOT inject that memory
- **AND** SHALL NOT return it from any memory query outside tenant T1 / workspace A

#### Scenario: Injected memory stays within budget

- **GIVEN** a workspace with more memories than the injection token budget allows
- **WHEN** the agent runs
- **THEN** the system SHALL inject a bounded selection (recent plus keyword-matched)
  within the budget
- **AND** SHALL NOT exceed the configured memory token budget

#### Scenario: Secrets are not stored in memory

- **GIVEN** the agent attempts to remember a note containing an API key or password
- **WHEN** the `remember` tool runs
- **THEN** the system SHALL reject the write
- **AND** SHALL NOT persist the secret

#### Scenario: Saving memory requires edit access

- **GIVEN** a caller with viewer-only access to the workspace
- **WHEN** the agent's `remember` tool is invoked on that caller's behalf
- **THEN** the system SHALL deny the write
- **AND** SHALL persist no memory

#### Scenario: User deletes a memory

- **GIVEN** a stored workspace memory the user can access
- **WHEN** the user deletes that memory
- **THEN** the system SHALL remove it
- **AND** SHALL NOT inject it into any subsequent agent run

### Requirement: Saved agent skills

The system SHALL let a workspace member save a named, reusable agent instruction
(a "skill") in the workspace, optionally with a short description and an
instruction template containing simple `{variable}` placeholders. Skills SHALL be
workspace- and tenant-scoped and shared with the workspace. Invoking a skill
SHALL expand its declared variables into a concrete instruction string and run
that instruction through the existing agent tool-loop against the current
document/workspace; a skill SHALL produce only instruction text and SHALL NOT
introduce any new agent-loop mechanics. Listing and running a skill SHALL require
workspace membership; creating and editing a skill SHALL require editor rights;
deleting a skill SHALL require the skill's creator or a workspace owner. Running a
skill SHALL respect the caller's permissions on the current document and
workspace and SHALL NOT widen access.

#### Scenario: Save a named skill

- **GIVEN** a workspace member with editor rights
- **WHEN** they save a skill with a name, optional description, and an
  instruction template
- **THEN** the system SHALL create the skill in that workspace
- **AND** the skill SHALL appear when the workspace's skills are listed

#### Scenario: Invoke a skill expands variables and runs it

- **GIVEN** a saved skill whose instruction template contains `{variable}`
  placeholders
- **WHEN** a member invokes the skill and supplies values for its variables
- **THEN** the system SHALL expand each `{variable}` into the supplied value to
  produce a concrete instruction string
- **AND** SHALL run that instruction through the agent tool-loop against the
  current document/workspace

#### Scenario: Skills are workspace and tenant scoped

- **GIVEN** a skill saved in one workspace of a tenant
- **WHEN** a member of a different workspace or a different tenant lists skills
- **THEN** that skill SHALL NOT be returned

#### Scenario: Only authorized roles create, edit, or delete

- **GIVEN** a workspace member with view-only rights
- **WHEN** they attempt to create, edit, or delete a skill
- **THEN** the operation SHALL be denied
- **AND** deleting a skill SHALL be permitted only for the skill's creator or a
  workspace owner

#### Scenario: Running a skill respects the caller's document permissions

- **GIVEN** a caller with view-only permission on the current document
- **WHEN** they run a skill whose instruction would edit the document
- **THEN** the edit SHALL be denied by the agent's permission checks
- **AND** the skill SHALL NOT grant any access the caller does not already have

### Requirement: Scheduled autonomous agent runs
The system SHALL let a user create a scheduled agent task with a name, a
natural-language instruction, a target workspace, an optional target document,
and a schedule (a cron-like expression) and/or a trigger. The system SHALL run
each enabled task autonomously in the background — with no live user present —
by invoking the existing agent tool-loop, SHALL write the run's result into a
document, and SHALL notify the task owner with a link to that document. Tasks
SHALL be listable, enable-able, and disable-able, and each SHALL expose its run
history.

#### Scenario: Create and schedule a task
- **GIVEN** an authenticated user in a workspace
- **WHEN** the user creates a task with an instruction, a target document, and a
  cron schedule
- **THEN** the system SHALL store the task with the creating user recorded as its
  owner and its tenant taken from the user's verified token
- **AND** the task SHALL appear in the user's task list as enabled with a
  computed next run time

#### Scenario: A due task runs without a live user
- **GIVEN** an enabled task whose next run time has arrived
- **WHEN** the scheduler evaluates due tasks
- **THEN** the system SHALL execute the task through the existing agent tool-loop
  with no live user token
- **AND** SHALL write the result into the task's target document through the CRDT
  attributed to the agent
- **AND** SHALL emit a notification to the task owner containing a link to that
  document

#### Scenario: A disabled task does not run
- **GIVEN** a task that has been disabled
- **WHEN** its scheduled time arrives
- **THEN** the system SHALL NOT execute it
- **AND** no run record SHALL be created for that occurrence

#### Scenario: A task is not double-run on a tick
- **GIVEN** a single due task and more than one scheduler evaluating due tasks
  concurrently
- **WHEN** they both attempt to claim the task on the same tick
- **THEN** the task SHALL be executed at most once
- **AND** the losing claimant SHALL skip the task

#### Scenario: Every run is audited
- **GIVEN** a background task execution
- **WHEN** the run finishes for any reason (success, failure, denied, or stopped)
- **THEN** the system SHALL write an audit record including the task id, the
  owner, the trigger, and the outcome

### Requirement: Background run safety limits
Because a background run has no user to confirm actions, the system SHALL disable
destructive tools (deleting a document or a block) in background mode unless the
task carries an explicit pre-approval, and SHALL enforce per-run limits on the
maximum number of tool rounds, maximum wall-clock time, and maximum number of
actions. On exceeding any limit the system SHALL stop the run and record which
limit was exceeded.

#### Scenario: Destructive tools are unavailable in background mode
- **GIVEN** a background run whose instruction would delete a block or document
- **WHEN** the agent attempts a destructive tool that is not pre-approved
- **THEN** the system SHALL NOT perform the deletion
- **AND** SHALL record the refusal in the run outcome

#### Scenario: A run that exceeds the tool-round limit is stopped
- **GIVEN** a background run configured with a maximum number of tool rounds
- **WHEN** the run reaches that number of rounds without completing
- **THEN** the system SHALL stop the run
- **AND** SHALL record the outcome as stopped for exceeding the round limit

#### Scenario: A run that exceeds the wall-clock limit is stopped
- **GIVEN** a background run configured with a maximum wall-clock time
- **WHEN** the run's elapsed time reaches that limit
- **THEN** the system SHALL stop the run
- **AND** SHALL record the outcome as stopped for exceeding the time limit

#### Scenario: A run that exceeds the action limit is stopped
- **GIVEN** a background run configured with a maximum number of actions
- **WHEN** the run performs that many actions without completing
- **THEN** the system SHALL stop the run
- **AND** SHALL record the outcome as stopped for exceeding the action limit

### Requirement: Owner-scoped background authorization
A background run SHALL be authorized from the task's stored owner, not from the
service identity used to authenticate outbound calls. The system SHALL execute
the run within the owner's tenant and SHALL evaluate the owner's current
document and workspace permissions at run time. The client-credentials service
token SHALL be used only as transport to sibling backends and SHALL NOT be
treated as the run's authority.

#### Scenario: Run acts within the owner's tenant and permissions
- **GIVEN** a task owned by a user in a given tenant
- **WHEN** the task runs in the background
- **THEN** the run SHALL operate strictly within that owner's tenant
- **AND** SHALL only access documents and workspaces the owner is permitted to
  access

#### Scenario: Run is denied when the owner has lost access
- **GIVEN** a task whose owner no longer has permission on the target document
- **WHEN** the task's scheduled time arrives and it runs
- **THEN** the system SHALL deny the run
- **AND** SHALL record the outcome as denied without writing to the document

#### Scenario: The service identity is never the authority
- **GIVEN** a background run authenticating to sibling backends with a
  client-credentials service token whose subject is the service client
- **WHEN** the system authorizes what the run may read or change
- **THEN** it SHALL derive authorization from the stored owner
- **AND** SHALL NOT grant the run any access based on the service identity

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

