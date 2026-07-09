# whiteboard-canvas Specification

## MODIFIED Requirements

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
