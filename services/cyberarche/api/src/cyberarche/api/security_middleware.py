"""Security middleware: response hardening headers + a light auth rate limit.

Addresses security-audit findings F-005 (missing security headers →
clickjacking + no XSS containment) and F-006 (no throttling on the credential
proxy → brute-force / credential stuffing).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # API responses are JSON; deny framing and script/object sources outright.
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client sliding-window limit on the credential-exchange endpoints.

    In-process (per replica) — a defence-in-depth floor against single-source
    brute force, not a substitute for a gateway/distributed limit at scale.
    Only the auth session endpoints are limited; everything else passes through.
    """

    def __init__(self, app, *, max_requests: int = 10, window_seconds: float = 60.0):
        super().__init__(app)
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _limited_path(self, path: str) -> bool:
        return path.startswith("/api/v1/auth/session")

    async def dispatch(self, request: Request, call_next):
        if not self._limited_path(request.url.path):
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = self._hits[client]
        while hits and now - hits[0] > self._window:
            hits.popleft()
        if len(hits) >= self._max:
            retry = int(self._window - (now - hits[0])) + 1
            return JSONResponse(
                {"error": "RateLimited", "detail": "too many attempts"},
                status_code=429,
                headers={"Retry-After": str(retry)},
            )
        hits.append(now)
        return await call_next(request)
