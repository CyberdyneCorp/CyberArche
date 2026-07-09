# Document-scoped connectors + per-session opt-in

## Why

Two clauses in `external-mcp-connectors` were built only in part:

- "Register an external MCP server for a workspace **or document**" — the
  `Connector` aggregate has only `workspace_id`; there is no document scope, so
  every connector is workspace-wide.
- "tools SHALL only be used **within sessions where the connector is enabled**"
  — enablement is a single workspace-global boolean (opt-*out*, default on).
  There is no per-session dimension: a connector is on for every session or none.

Both had a scenario for the implemented half, so `--strict` did not catch the
missing half.

## What Changes

- `Connector` gains an optional `document_id`. A document-scoped connector is
  active only when the agent is working on that document; a workspace-scoped
  connector (no document) is active for every document in the workspace.
  Registration takes an optional document id; a document-scoped connector is
  removed when its document is purged (FK cascade).
- Per-session opt-in: `tools()`/`call()` accept an optional allow-set of
  connector ids for the current session. When given, only those connectors are
  offered/dispatched (still subject to the owner's global enable). The agent
  `ask` threads this through, and `POST /agent/ask` accepts `enabled_connectors`.
  The existing global enable/disable remains the owner's admin control.

## Non-goals

- A dedicated per-document connector registration UI, and per-conversation
  connector toggles in the agent panel — the backend + API make both reachable;
  the UI can follow.
- Changing credential encryption, namespacing, or the handshake check.

## Impact

- `external-mcp-connectors`: the document-scope and per-session halves gain
  scenarios.
- Data model: `mcp_connectors.document_id` column + migration; the connector
  port-contract test covers scope. Document scope cascades on purge.
- The agent's tool-gathering and dispatch thread the session allow-set.
