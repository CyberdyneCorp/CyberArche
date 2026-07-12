# ai-agent Specification

## ADDED Requirements

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
