# ai-agent Specification

## ADDED Requirements

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
