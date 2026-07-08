"""AgentRunRepository adapter over the agent_runs table."""

from __future__ import annotations

import json

import asyncpg

from cyberarche.application.ports.agent import AgentRun
from cyberarche.domain.ids import AgentRunId, DocumentId, TenantId, UserId


class PostgresAgentRunRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, run: AgentRun) -> None:
        await self._pool.execute(
            """
            INSERT INTO agent_runs
                (id, tenant_id, document_id, user_id, model, prompt,
                 tools_used, outcome, started_at, finished_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            run.id,
            run.tenant_id,
            run.document_id,
            run.user_id,
            run.model,
            run.prompt,
            json.dumps(list(run.tools_used)),
            run.outcome,
            run.started_at,
            run.finished_at,
        )

    async def list_for_document(
        self, tenant_id: TenantId, document_id: DocumentId
    ) -> list[AgentRun]:
        rows = await self._pool.fetch(
            """
            SELECT * FROM agent_runs
            WHERE tenant_id = $1 AND document_id = $2
            ORDER BY started_at DESC
            """,
            tenant_id,
            document_id,
        )
        return [
            AgentRun(
                id=AgentRunId(row["id"]),
                tenant_id=TenantId(row["tenant_id"]),
                user_id=UserId(row["user_id"]),
                document_id=DocumentId(row["document_id"]) if row["document_id"] else None,
                model=row["model"],
                prompt=row["prompt"],
                tools_used=tuple(json.loads(row["tools_used"])),
                outcome=row["outcome"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
            )
            for row in rows
        ]
