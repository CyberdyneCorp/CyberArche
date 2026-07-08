#!/usr/bin/env python3
"""Apply pending SQL migrations from db/migrations in filename order.

Usage: DATABASE_URL=postgres://... uv run python scripts/migrate.py
Applied migrations are tracked in schema_migrations.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import asyncpg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "db" / "migrations"


async def migrate(database_url: str) -> None:
    connection = await asyncpg.connect(database_url)
    try:
        await connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                name       TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        applied = {
            row["name"]
            for row in await connection.fetch("SELECT name FROM schema_migrations")
        }
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in applied:
                continue
            print(f"applying {path.name} ...")
            await connection.execute(path.read_text())
            await connection.execute(
                "INSERT INTO schema_migrations (name) VALUES ($1)", path.name
            )
        print("migrations up to date")
    finally:
        await connection.close()


if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL") or os.environ.get("CYBERARCHE_DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL (or CYBERARCHE_DATABASE_URL) is required")
    asyncio.run(migrate(url))
