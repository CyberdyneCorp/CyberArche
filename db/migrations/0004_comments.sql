-- 0004_comments: block-anchored comments (permissions-sharing spec)

BEGIN;

CREATE TABLE comments (
    id           TEXT PRIMARY KEY,
    document_id  TEXT NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    block_id     TEXT NOT NULL,
    author_id    TEXT NOT NULL,
    body         TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL,
    resolved_at  TIMESTAMPTZ,
    resolved_by  TEXT
);
CREATE INDEX comments_document_idx ON comments (document_id, created_at);

COMMIT;
