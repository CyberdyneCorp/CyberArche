# Tasks

## Backend — file upload + serve
- [x] `FileUseCases.upload_image` (workspace EDITOR, size cap, magic-byte MIME sniff) and `get_file` (workspace VIEWER)
- [x] `routers/files.py`: `POST /workspaces/{id}/files` (multipart) + `GET /workspaces/{id}/files/{file_id}`; register router
- [x] Add `files` to the UseCases container and wiring

## Backend — image generation port + adapter
- [x] `ports/images.py`: `ImageGenerationPort` + `GeneratedImage`
- [x] `adapters/outbound/imagegen/openai_images.py`: OpenAI `images/generations` (gpt-image-1)
- [x] `ScriptedImageGenerator` fake for tests
- [x] Wiring: `image_*` config, build the generator, thread into AgentUseCases + FileUseCases; `CYBERARCHE_IMAGE_*` settings

## Backend — agent tool
- [x] `generate_image` tool: generate → store blob → insert `image` block; mark as an editing action
- [x] Extend `insert_blocks` tool description with `image`/`embed` shapes; normalize image `src`→`url`

## Backend tests
- [x] Upload: valid image stored+served; oversized rejected; disguised non-image rejected; non-member denied
- [x] Agent `generate_image` inserts an image block (fake image port); reports unavailable when unconfigured

## Frontend
- [x] `postForm` helper in `http.ts`; `api/files.ts` `uploadImage`
- [x] `AuthImage.svelte` (authenticated fetch → object URL) for internal `/api/` image URLs
- [x] `ImageBlock.svelte` (URL paste + upload) and register `image`
- [x] `editor/embeds.ts` (parse YouTube/Vimeo/Loom/generic) + `EmbedBlock.svelte`; register `embed`

## Frontend tests
- [x] vitest: `embeds.ts` provider parsing (youtube/vimeo/generic/non-https)
- [x] e2e: image block via URL, YouTube embed, and image upload

## Verify
- [x] Backend suite + Postgres contracts, vitest, full e2e, typecheck, import-linter
