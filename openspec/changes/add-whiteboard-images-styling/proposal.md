# Whiteboard images + per-element styling

## Why

`whiteboard-canvas` "Canvas primitives" promises "rectangles, ellipses,
diamonds, arrows/connectors, freehand strokes, text labels, **and images**,
with **styling (color, stroke, fill)**." Neither is built: the element kind
union has no `image`, and elements carry no style fields — every shape renders
with the same fixed CSS variables. The requirement's only scenario ("Connect
two shapes") exercises neither, so `--strict` passed.

## What Changes

- Image primitive: a new `image` element kind carrying a `src` (embedded data
  URL, so it travels in the CRDT/snapshot like any other element). An image
  tool on the toolbar opens a file picker, reads the file as a data URL, and
  places it on the canvas.
- Per-element styling: elements gain optional `fill`, `stroke`, and `color`
  (label colour). Shapes render with their own style, falling back to the
  current defaults when unset. Selecting a shape reveals a small style control
  (fill + stroke swatches) that writes the style through the CRDT, so styling
  merges and persists like position and label.

## Non-goals

- Uploading images to blob storage — embedding as a data URL keeps them in the
  scene with no new storage path (large images are the user's discretion).
- Stroke width / dash / opacity, gradients, or z-order — colour, stroke colour,
  and fill only, matching the clause.

## Impact

- `whiteboard-canvas`: the image and styling halves of Canvas primitives gain
  scenarios.
- Frontend only; the scene data model gains optional fields (backward-compatible
  — existing scenes omit them). Covered by whiteboard VM vitest and e2e.
