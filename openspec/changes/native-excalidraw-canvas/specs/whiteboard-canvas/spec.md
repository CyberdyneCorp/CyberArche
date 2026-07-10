# whiteboard-canvas Specification

## ADDED Requirements

### Requirement: Native Excalidraw block

The system SHALL provide an `excalidraw` block backed by the
`@cyberdynecorp/excalidraw-svelte` engine, embedding an infinite Excalidraw
canvas inside a document. The block SHALL support the engine's drawing tools
(selection, rectangle, diamond, ellipse, line, arrow, freehand, text, image,
eraser), pan and zoom, undo and redo, and deletion of the selection.

#### Scenario: Create and edit an excalidraw block

- **WHEN** a user inserts an `excalidraw` block and draws shapes
- **THEN** the shapes SHALL render on the canvas
- **AND** reopening the document SHALL restore the scene

#### Scenario: Legacy whiteboard still renders

- **WHEN** a document contains a legacy `whiteboard` block
- **THEN** that block SHALL still render with the legacy canvas
- **AND** new diagram blocks offered in the slash menu SHALL be `excalidraw`

### Requirement: Excalidraw collaborative editing

The `excalidraw` block SHALL bind its `EditorStore` to the document's shared
Y.Doc through the `@cyberdynecorp/excalidraw-yjs` adapter, storing its elements
in a per-block root map so concurrent edits to different elements merge, and so
the scene syncs and persists through the existing realtime transport without a
transport change.

#### Scenario: Two users edit the same board

- **WHEN** two users edit different elements of the same `excalidraw` block
  concurrently
- **THEN** both edits SHALL survive and converge on every client

#### Scenario: Scene mirrored for export and agent

- **WHEN** an `excalidraw` scene changes
- **THEN** the block SHALL mirror the serialized scene into its `data.scene`
- **AND** document export and the agent SHALL read the scene from there
