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

### Requirement: Graph explorer interactions

The graph view SHALL help the user read the structure, not only display it. It
SHALL draw edges directed (source → target) with arrowheads, auto-fit the graph
to the view on open (and offer a Fit control), and size a node by how connected
it is. Selecting a node SHALL open an inspector showing its connection counts
(incoming, outgoing, total) and its neighbours, dim the unrelated nodes, and
offer to open the document. The view SHALL provide search to focus a document by
title and report how many documents are isolated (no links).

#### Scenario: Inspect a node

- **WHEN** the user clicks a node
- **THEN** an inspector SHALL show its incoming, outgoing, and total connection
  counts and its neighbouring documents
- **AND** the node's neighbours SHALL be highlighted while the rest are dimmed

#### Scenario: Fit and orient the graph

- **WHEN** the graph opens
- **THEN** it SHALL be scaled and centred to fit the view
- **AND** edges SHALL show direction with arrowheads

### Requirement: Graph analytics

The graph view SHALL compute analytics from the documents and links and present
them in plain language. It SHALL group documents into clusters (communities) and
colour nodes by cluster, report centrality so the user can see a document's role
(most connected, a bridge between topics, a good starting point, an
authoritative document), surface structural insights (isolated documents,
documents with no incoming references, and the number of disconnected groups),
and let the user trace the shortest path between two documents.

#### Scenario: See a document's role and cluster

- **WHEN** the user selects a node
- **THEN** the inspector SHALL show its cluster and centrality
- **AND** SHALL label it as most connected, a bridge, a best starting point, or
  authoritative when it is the top document for that measure

#### Scenario: Surface structural insights

- **WHEN** the graph loads
- **THEN** the view SHALL report the number of clusters and disconnected groups
- **AND** SHALL flag isolated documents and documents with no incoming references

#### Scenario: Trace how two documents relate

- **WHEN** the user selects a document, chooses "Find path to…", and clicks
  another document
- **THEN** the view SHALL highlight the shortest path of links between them

### Requirement: Graph layouts and navigation

The graph view SHALL offer multiple layouts — force-directed, hierarchical
(directed layering), radial (rings by hop distance from a focus), and clustered
(grouped by community) — selectable by the user. It SHALL provide a depth control
that, when a node is selected, limits the graph to that node's N-hop
neighbourhood, and a minimap giving an overview of the whole graph and the
current viewport.

#### Scenario: Switch layout

- **WHEN** the user chooses a different layout
- **THEN** the nodes SHALL be re-positioned according to that layout

#### Scenario: Focus a local neighbourhood

- **WHEN** a node is selected and a depth of N is chosen
- **THEN** only documents within N links of the selected node SHALL be shown
