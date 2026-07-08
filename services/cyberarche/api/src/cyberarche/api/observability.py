"""Minimal request observability: structured access log with timing."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request

logger = logging.getLogger("cyberarche.api")


def install_observability(app: FastAPI) -> None:
    @app.middleware("http")
    async def access_log(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "%s %s -> %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
