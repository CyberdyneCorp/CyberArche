# document-links Specification

## ADDED Requirements

### Requirement: AI-inferred typed relationships

The system SHALL infer typed relationships between the documents in a teamspace
or folder using the language model: for a document it SHALL classify its
relationships to the other in-scope documents as one of `depends_on`,
`explains`, `cites`, `similar`, `contradicts`, or `mentions`, each with a
confidence and a short evidence string, dropping low-confidence relationships.
The inferred graph SHALL be returned alongside the explicit `[[link]]` edges,
with each edge marked as inferred or explicit and carrying its type, confidence,
and evidence. Only documents the caller may view SHALL appear.

#### Scenario: Inferred relationships are typed

- **WHEN** the caller requests the inferred graph for a folder
- **THEN** the response SHALL include the explicit `[[link]]` edges
- **AND** additional inferred edges each carrying a type, a confidence, and
  evidence, marked as inferred

### Requirement: Inference results are cached per document

Inferred relationships SHALL be cached per source document, keyed by a hash of
that document's content. When the inferred graph is requested, a document SHALL
be re-classified only if it is new or its content changed since it was last
classified; unchanged documents SHALL be served from the cache. Re-requesting
the inferred graph without changing any document SHALL make no language-model
calls.

#### Scenario: Re-opening the graph does not re-ask the model

- **GIVEN** the inferred graph for a folder was computed once
- **WHEN** the inferred graph is requested again and no document changed
- **THEN** the cached relationships SHALL be returned
- **AND** the language model SHALL NOT be called

#### Scenario: Only changed documents are re-inferred

- **GIVEN** the inferred graph was computed
- **WHEN** one document's content changes and the graph is requested again
- **THEN** only that document SHALL be re-classified by the model
