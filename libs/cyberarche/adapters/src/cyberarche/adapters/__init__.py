"""CyberArche adapters: inbound (HTTP, MCP) and outbound (Postgres, Auth, ...).

Inbound adapters must never import outbound adapters (enforced by import-linter);
they meet only in wiring/, the composition root.
"""
