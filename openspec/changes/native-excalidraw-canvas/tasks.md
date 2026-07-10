# Tasks

## 1. Build plumbing (private registry)
- [x] 1.1 Add `apps/cyberarche/web/.npmrc` referencing `${NPM_GITHUB_TOKEN}` (no token in repo)
- [x] 1.2 Add `@cyberdynecorp/excalidraw-svelte` + `@cyberdynecorp/excalidraw-yjs` deps
- [x] 1.3 Web Dockerfile: `ARG NPM_GITHUB_TOKEN` + copy `.npmrc` before `pnpm install`
- [x] 1.4 `docker-compose.yml` web `build.args: NPM_GITHUB_TOKEN`
- [x] 1.5 Set Coolify `NPM_GITHUB_TOKEN` (build-time)

## 2. Backend
- [x] 2.1 Whitelist `excalidraw` in `domain/blocks.py` `BLOCK_TYPES`
- [x] 2.2 Regression test: `excalidraw` accepted, unknown type still rejected

## 3. Frontend block
- [x] 3.1 `ExcalidrawBlock.svelte`: canvas host (render loop + pointer + pan/zoom), toolbar, on-canvas text edit
- [x] 3.2 Bind `YjsCollab(store, vm.doc, { elementsKey: 'excalidraw:'+block.id })`
- [x] 3.3 Debounced mirror of `store.documentJSON()` into `data.scene`
- [x] 3.4 Seed store from `data.scene` on first open (agent-created / legacy)
- [x] 3.5 Register `excalidraw` block; keep `whiteboard` for old docs
- [x] 3.6 Respect `editor.readOnly`

## 4. Agent
- [x] 4.1 `_render_block` describes an `excalidraw` scene (shapes + labels + links)
- [x] 4.2 `create_mindmap` tool emits a valid `.excalidraw` scene into the block
- [x] 4.3 Tests for scene rendering + mindmap generation

## 5. Validate
- [x] 5.1 `openspec validate native-excalidraw-canvas --strict`
- [x] 5.2 Web typecheck + unit tests; backend tests green
