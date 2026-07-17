# Workspace-wide chat ("Chat with your workspace")

## Why

The agent is document-scoped — you must open a doc to ask it anything. There's
no place to ask a question across the *whole* workspace. The RAG knowledge base
and the new full-text search already exist; this composes them into a
conversational, workspace-level chat grounded in the workspace's documents.

## What Changes

- Add `WorkspaceChatUseCases.ask(caller, workspace_id, instruction, history)`:
  retrieve (RAG answer over the workspace's project + top full-text search hits),
  then synthesize one conversational answer with the LLM using recent history
  and the workspace persona/instructions. Returns the answer plus the source
  documents it drew on. Read-only — it never edits documents.
- New endpoint `POST /workspaces/{id}/chat`.
- A "Chat with workspace" surface (sidebar entry → chat panel): message thread,
  input, and clickable source citations.

## Impact

- Affected specs: `ai-agent`.
- Affected code: new `application/use_cases/workspace_chat.py` (composes the
  existing knowledge + search use cases + LLM + persona); `use_cases/__init__.py`
  + wiring; a chat router; a `WorkspaceChat` component + viewmodel + `api/chat.ts`.
  No migration.
