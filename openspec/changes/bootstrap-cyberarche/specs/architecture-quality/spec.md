# architecture-quality Specification

## Purpose

Scalability and maintainability are first-class, non-functional requirements for
CyberArche: the platform MUST be easy to extend with new features (block types,
LLM providers, tools, inbound surfaces) and MUST scale horizontally under load.
These requirements constrain every other capability.

## ADDED Requirements

### Requirement: Enforced hexagonal boundaries
The codebase SHALL enforce the dependency rule `domain <- application <-
adapters` (inbound never importing outbound) with an automated check in CI, so a
new feature cannot couple layers or leak infrastructure into the domain.

#### Scenario: Boundary violation fails CI
- **WHEN** a change introduces an import that violates the layer dependency rule
- **THEN** the CI boundary check (import-linter) SHALL fail the build

#### Scenario: Feature added without touching the domain
- **WHEN** a feature is added that only needs a new adapter or use case
- **THEN** it SHALL be addable without modifying domain code

### Requirement: Pluggable block types
Adding a new block type SHALL require only registering it in the block-type
registry and providing its render/serialize logic, without modifying the core
editor engine, CRDT sync, or unrelated block implementations.

#### Scenario: Register a new block type
- **WHEN** a developer adds a new block type via the registry
- **THEN** the editor, slash menu, and persistence SHALL support it without
  changes to existing block types
- **AND** existing documents SHALL continue to load unchanged

### Requirement: Pluggable providers behind ports
Provider-specific concerns — LLM, RAG, auth, storage, CRDT engine — SHALL sit
behind application ports so an implementation can be added or swapped by
configuration without changing use cases or domain code.

#### Scenario: Add an LLM provider
- **WHEN** a new LLM provider adapter is added and selected by configuration
- **THEN** the agent use cases SHALL work with it unchanged

#### Scenario: Swap an outbound adapter
- **WHEN** an outbound adapter (e.g. storage) is replaced with another
  implementing the same port
- **THEN** no application or domain code SHALL require changes

### Requirement: Multiple inbound surfaces over shared use cases
New inbound surfaces (HTTP, MCP, workers, future transports) SHALL be thin
adapters over the same application use cases and single composition root, so
behavior and authorization are defined once and cannot diverge per surface.

#### Scenario: New surface reuses use cases
- **WHEN** a new inbound surface exposes an existing capability
- **THEN** it SHALL delegate to the existing use cases rather than reimplement
  the logic

### Requirement: Horizontal scalability of stateless services
The HTTP API and MCP server SHALL be stateless so they scale horizontally behind
a load balancer; all shared state SHALL live in Postgres, object storage, or the
CRDT/update log rather than in process memory.

#### Scenario: Scale API replicas
- **WHEN** additional API/MCP replicas are added
- **THEN** any replica SHALL serve any request correctly without sticky sessions

### Requirement: Scalable realtime and background work
The realtime relay SHALL support running multiple instances that share document
CRDT state via the persisted update log / a shared broker, and long-running or
bulk work (ingestion, large agent runs) SHALL execute on horizontally scalable
workers via a queue rather than in request handlers.

#### Scenario: Multiple realtime instances
- **WHEN** two clients editing the same document connect to different relay
  instances
- **THEN** their edits SHALL still converge via shared CRDT state

#### Scenario: Ingestion offloaded to workers
- **WHEN** a large file is ingested
- **THEN** the work SHALL be enqueued to workers and SHALL NOT block the request
  or the editor

### Requirement: Maintainability budgets
The codebase SHALL keep per-function cognitive complexity within the project
budgets (backend ≤15, frontend 8–12) and SHALL gate this in CI on changed files,
so features stay readable and easy to extend.

#### Scenario: Complexity regression flagged
- **WHEN** a changed function exceeds its cognitive-complexity budget
- **THEN** the CI complexity gate SHALL flag it for refactor

### Requirement: Contract parity across adapters
The system SHALL cover adapters implementing the same port (e.g. real vs
in-memory fake, or two provider adapters) with a shared contract test suite, so
new implementations are verified against the same behavior.

#### Scenario: New adapter runs the contract suite
- **WHEN** a new adapter for an existing port is added
- **THEN** it SHALL pass the port's shared contract tests before use
