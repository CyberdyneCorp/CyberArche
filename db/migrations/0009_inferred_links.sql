-- 0009_inferred_links: cache of AI-inferred typed relationships between
-- documents, keyed per source document by a hash of its content. Lets the graph
-- explorer show typed/inferred edges without re-asking the LLM on every open;
-- a row is recomputed only when its document's content_hash changes.

BEGIN;

CREATE TABLE document_inferred_links (
    source_document_id TEXT PRIMARY KEY
        REFERENCES documents (id) ON DELETE CASCADE,
    tenant_id          TEXT NOT NULL,
    content_hash       TEXT NOT NULL,
    computed_at        TIMESTAMPTZ NOT NULL,
    -- [{target_title, type, confidence, evidence}, ...]
    payload            JSONB NOT NULL
);
CREATE INDEX document_inferred_links_tenant_idx
    ON document_inferred_links (tenant_id);

ALTER TABLE document_inferred_links ENABLE ROW LEVEL SECURITY;
CREATE POLICY document_inferred_links_tenant_isolation ON document_inferred_links
    USING (tenant_id = current_setting('cyberarche.tenant_id', TRUE));

COMMIT;
