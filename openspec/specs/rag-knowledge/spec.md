# rag-knowledge Specification

## Purpose

CyberdyneRAG-backed workspace knowledge: isolated per-workspace projects, the ingestion pipeline, retrieval modes, and lifecycle cascades.

## Requirements

### Requirement: Workspace-to-RAG project mapping
Each workspace SHALL map to an isolated CyberdyneRAG project (`project_slug`), so
a workspace's knowledge never leaks across tenants or workspaces.

#### Scenario: Provision a RAG project
- **WHEN** a workspace is created
- **THEN** the system SHALL ensure a corresponding isolated RAG project exists

#### Scenario: Isolation across workspaces
- **WHEN** a query runs against a workspace's RAG project
- **THEN** results SHALL only include documents ingested into that workspace

### Requirement: File ingestion pipeline
The system SHALL ingest supported files (PDF, DOCX, XLS/XLSX, MD, TXT, CSV, JSON)
into a workspace's RAG project by uploading to CyberdyneRAG and tracking the
returned task to completion.

#### Scenario: Track ingestion to completion
- **WHEN** a file is uploaded for ingestion
- **THEN** the system SHALL record the RAG task and poll (or receive a callback)
  until it reports completed or failed

#### Scenario: Deduplicate re-ingestion
- **WHEN** the same file content is ingested again without forcing reprocessing
- **THEN** the system SHALL rely on RAG deduplication and not create a duplicate

### Requirement: Retrieval queries
The system SHALL run retrieval queries against a workspace's RAG project,
supporting the available query modes (local, global, hybrid, naive, mix), and
return results for use by the agent and by callers.

#### Scenario: Hybrid query
- **WHEN** the agent runs a retrieval query in hybrid mode
- **THEN** the system SHALL return the RAG results for grounding its answer

### Requirement: Document lifecycle in RAG
When a document or uploaded source is deleted, the system SHALL remove the
corresponding datasource from the workspace's RAG project.

#### Scenario: Delete cascades to RAG
- **WHEN** an ingested source is deleted from a workspace
- **THEN** the system SHALL delete its datasource from the RAG project
