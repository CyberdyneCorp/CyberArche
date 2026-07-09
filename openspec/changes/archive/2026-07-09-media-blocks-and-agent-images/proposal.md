# Media blocks, file uploads, and agent image generation

## Why
Documents can hold text, code, math, diagrams, tables, and whiteboards, but not
images or embedded video. Users want to drop images (uploaded or by URL) and
embed YouTube/other players into a document, and want the AI agent to be able to
generate an image and place it in the document. The backend block whitelist
already reserves `image`, `file`, and `embed` types, but there are no editor
components, no way to upload/serve a file, and no image-generation capability.

## What Changes
- **Image block** (`image`): renders an image from a URL. Empty blocks offer
  "paste image URL" and "upload". Uploaded images are stored in blob storage and
  referenced by a served URL, so the CRDT document stays light.
- **Embed block** (`embed`): renders YouTube, Vimeo, and Loom as responsive
  players, and any other `https` URL as a sandboxed iframe with an open-link
  fallback. Only `https` is accepted; the iframe is sandboxed.
- **File upload + serve** (new capability): `POST /workspaces/{id}/files`
  (multipart) stores an image after validating it — a size cap and a magic-byte
  MIME check (png/jpeg/gif/webp only; no SVG) — and returns a served URL.
  `GET /workspaces/{id}/files/{file_id}` streams the bytes to workspace members
  (authenticated).
- **Agent image generation** (ai-agent): a `generate_image` tool lets the agent
  create an image from a prompt via OpenAI `gpt-image-1`, store it, and insert an
  image block into the open document as a CRDT peer. Configured by
  `CYBERARCHE_IMAGE_*`; absent config → the tool reports it is unavailable.
- The agent's `insert_blocks` tool description is extended to teach the model the
  `image` and `embed` data shapes.

## Impact
- New specs: `file-uploads`. Modified: `block-editor` (image + embed blocks),
  `ai-agent` (image generation). `document-model` already whitelists the types.
- New code: `ports/images.py`, `adapters/outbound/imagegen/openai_images.py`,
  `use_cases/files.py`, `routers/files.py`; web `ImageBlock.svelte`,
  `EmbedBlock.svelte`, `AuthImage.svelte`, `editor/embeds.ts`, `api/files.ts`,
  a `postForm` HTTP helper, and two `registerBlock` calls.
- Security: uploads are size-capped and MIME-sniffed (no SVG/script payloads);
  the serve route requires workspace membership; embeds are `https`-only and
  sandboxed. Image generation needs a configured OpenAI key (`CYBERARCHE_IMAGE_API_KEY`).
- Known limitation (deferred): share-link viewers who are not workspace members
  cannot load uploaded images (the serve route is membership-gated).
