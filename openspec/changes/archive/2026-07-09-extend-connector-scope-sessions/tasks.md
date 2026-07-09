# Tasks

## 1. Data model + domain
- [x] 1.1 `Connector.document_id: DocumentId | None`
- [x] 1.2 Migration: `mcp_connectors.document_id` nullable, `REFERENCES documents ON DELETE CASCADE`

## 2. Application
- [x] 2.1 `register(..., document_id=None)` stores the scope
- [x] 2.2 `tools(caller, ws, *, document_id=None, session_connectors=None)` — scope + session filter
- [x] 2.3 `call(...)` honours scope + session filter
- [x] 2.4 Agent threads a session allow-set through `_available_tools`/`ask`
- [x] 2.5 Tests: doc-scoped tool visible only on its doc; session allow-set narrows; disabled never offered

## 3. Adapters + API
- [x] 3.1 Postgres/in-memory connector repos map `document_id`
- [x] 3.2 Connector port-contract test covers document scope
- [x] 3.3 HTTP: register accepts optional `document_id`; `POST /agent/ask` accepts `enabled_connectors`
