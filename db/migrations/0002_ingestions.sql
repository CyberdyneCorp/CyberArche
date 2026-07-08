-- 0002_ingestions: RAG ingestion tracking (rag-knowledge spec)

BEGIN;

CREATE TABLE ingestion_tasks (
    task_id       TEXT PRIMARY KEY,
    workspace_id  TEXT NOT NULL REFERENCES workspaces (id) ON DELETE CASCADE,
    filename      TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    status        TEXT NOT NULL
        CHECK (status IN ('pending', 'converting', 'processing', 'completed', 'failed')),
    error         TEXT,
    created_at    TIMESTAMPTZ NOT NULL
);
CREATE INDEX ingestion_tasks_workspace_idx ON ingestion_tasks (workspace_id);
CREATE INDEX ingestion_tasks_hash_idx ON ingestion_tasks (workspace_id, content_hash);

COMMIT;
