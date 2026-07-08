"""CyberArche workers deployable.

Skeleton for now: ingestion and agent jobs land with the rag-knowledge and
ai-agent task groups, sharing the same composition root as the API.
"""

from __future__ import annotations


def run() -> None:  # pragma: no cover - wired up in groups 7-8
    raise SystemExit("cyberarche-workers: jobs land with the rag/agent tasks")
