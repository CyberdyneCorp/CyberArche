# whiteboard-canvas Specification

## Purpose

The native Excalidraw-style canvas block: shapes, bound connectors, freehand, and mind maps, collaboratively editable.
## Requirements
### Requirement: Embedded whiteboard block
The system SHALL provide a `whiteboard` block that embeds an Excalidraw-style
infinite canvas inside a document, storing its scene (elements, positions,
styles) as structured data within the document CRDT.

#### Scenario: Create and edit a whiteboard
- **WHEN** a user inserts a `whiteboard` block and draws shapes
- **THEN** the canvas scene SHALL persist as part of the document
- **AND** reopening the document SHALL restore the scene

### Requirement: Canvas primitives
The whiteboard SHALL support rectangles, ellipses, diamonds, arrows/connectors,
freehand strokes, text labels, and images, with per-element styling (label
colour, stroke colour, and fill). Images SHALL be embedded in the scene so they
persist and sync like any other element. Styling SHALL be applied per element
and SHALL persist and merge through the document CRDT.

#### Scenario: Connect two shapes
- **WHEN** a user draws a connector between two shapes
- **THEN** the connector SHALL bind to both, and follow them when they move

#### Scenario: Place an image
- **WHEN** a user adds an image to the canvas
- **THEN** an image element SHALL appear at that position
- **AND** the image SHALL be embedded in the scene so it persists and syncs

#### Scenario: Style a shape
- **WHEN** a user sets a shape's fill or stroke colour
- **THEN** the shape SHALL render with that style
- **AND** the style SHALL persist in the scene

#### Scenario: Styling is per element
- **WHEN** one shape is styled
- **THEN** other shapes SHALL keep their own styling

### Requirement: Mind maps
The whiteboard SHALL support mind maps as connected nodes with a root and
child branches, creatable manually and generatable by the AI agent from
document content.

#### Scenario: Generate a mind map from a document
- **WHEN** a user asks the agent to create a mind map of the current document
- **THEN** the system SHALL produce a `whiteboard` block containing a root node
  and branch nodes derived from the document's structure

#### Scenario: Add a child node
- **WHEN** a user adds a child to a mind-map node
- **THEN** the new node SHALL be connected to its parent

### Requirement: Collaborative canvas editing
Whiteboard edits SHALL merge conflict-free across concurrent editors via the
document CRDT, consistent with the realtime-collaboration capability.

#### Scenario: Concurrent shape edits
- **WHEN** two users move different shapes at the same time
- **THEN** both moves SHALL be preserved after sync

