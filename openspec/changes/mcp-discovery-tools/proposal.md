# MCP workspace/teamspace discovery tools

## Why

The MCP server lets a client search/read/create documents, but there was no way
to discover the workspaces or teamspaces to create in — yet create_document,
rag_query, and ingest_file all require a workspace_id. An MCP client could only
learn a workspace id by searching for an existing document. And MCP-created
documents could not be placed in a shared teamspace.

## What Changes

- Add MCP tools `list_workspaces` (the caller's workspaces) and
  `list_teamspaces(workspace_id)` (a workspace's teamspaces the caller can see).
- `create_document` gains an optional `teamspace_id` so a shared document can be
  created in a teamspace over MCP.

## Impact

- Affected specs: `mcp-server`.
- Affected code: `adapters/inbound/mcp/server.py`. Access is unchanged — the
  tools return only what the authenticated caller may see; document creation
  still enforces workspace/teamspace membership.
