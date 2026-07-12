# Native Excalidraw canvas

## Why

The `whiteboard` block is a hand-rolled SVG canvas with a small fixed set of
primitives. CyberdyneCorp maintains a real Excalidraw port,
`@cyberdynecorp/excalidraw-svelte` (headless `EditorStore` engine, `.excalidraw`
v2 format, Svelte 5), plus a Yjs adapter `@cyberdynecorp/excalidraw-yjs`
(`YjsCollab`, element-level CRDT). Adopting them gives us the full Excalidraw
toolset (roughjs strokes, arrows with bindings, sticky notes, tables, mermaid,
flowchart nodes, images, laser pointer) and true field-level collaborative
merge, and lets the AI agent generate real diagrams (mind maps, flowcharts) as
valid scenes.

We standardize on `excalidraw-native` and DO NOT embed excalidraw.com. Gaps in
the library are filed as issues upstream (a drop-in component request is filed
as excalidraw-native#24).

## What Changes

- Add a new `excalidraw` block backed by `@cyberdynecorp/excalidraw-svelte`,
  bound to the document's shared Y.Doc through `@cyberdynecorp/excalidraw-yjs`
  (`YjsCollab` on a per-block root map `excalidraw:<blockId>`), so it co-edits
  live and persists through the existing realtime transport with no backend
  transport change.
- Whitelist `excalidraw` in the backend block types.
- Mirror the scene JSON into the block's `data.scene` (debounced) so document
  export, snapshots, and the agent have a durable, parseable representation.
- Keep the legacy `whiteboard` block registered so existing documents still
  render; `excalidraw` becomes the diagram block offered in the slash menu.
- The AI agent SHALL describe an `excalidraw` scene when reading a document, and
  SHALL be able to create a diagram (e.g. a mind map) as a valid `.excalidraw`
  scene via a `create_mindmap` tool.
- Wire the private `@cyberdynecorp` GitHub Packages registry into the web
  Docker build (`.npmrc` + `NPM_GITHUB_TOKEN` build arg).

## Impact

- Affected specs: `whiteboard-canvas` (new native block), `ai-agent`
  (read/create excalidraw scenes).
- Affected code: web block registry + new `ExcalidrawBlock.svelte` + canvas
  host; `domain/blocks.py` whitelist; agent use case (`_render_block`,
  `create_mindmap`); web Dockerfile / `.npmrc` / `docker-compose.yml`.
- No change to the realtime transport, persistence, or auth.
