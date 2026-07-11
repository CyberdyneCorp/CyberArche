# document-links Specification

## ADDED Requirements

### Requirement: Link graph for a teamspace or folder

The system SHALL provide, for a teamspace or a folder, a link graph whose nodes
are the documents in that scope and whose edges are the resolved `[[title]]`
wikilinks between those documents. Title resolution SHALL be case-insensitive
(matching the wikilink rules), self-links SHALL be excluded, and duplicate edges
SHALL be collapsed. The graph SHALL include only documents the caller may view.

#### Scenario: Edges connect linked documents in scope

- **GIVEN** documents A and B are in the same teamspace
- **AND** A contains `[[B's title]]`
- **WHEN** the caller requests that teamspace's graph
- **THEN** the graph SHALL contain nodes for A and B
- **AND** an edge from A to B

#### Scenario: Links outside the scope are not edges

- **GIVEN** a document in the scope links to a document not in the scope
- **WHEN** the graph is requested
- **THEN** that link SHALL NOT appear as an edge in the graph

#### Scenario: Unreadable documents are excluded

- **WHEN** the caller cannot view a document in the scope
- **THEN** that document SHALL NOT appear as a node in the graph

### Requirement: Graph view over documents

The web app SHALL let a user open a graph view for a teamspace or folder from
its context menu. The view SHALL be a modal presenting the link graph, and the
user SHALL be able to zoom in and out and pan the graph. Double-clicking a node
SHALL close the modal and open that document.

#### Scenario: Open the graph from the context menu

- **WHEN** the user right-clicks a teamspace or folder and chooses "Open graph"
- **THEN** a modal graph of that scope's documents and their links SHALL appear

#### Scenario: Navigate to a document from the graph

- **WHEN** the user double-clicks a node in the graph
- **THEN** the modal SHALL close
- **AND** that node's document SHALL open
