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


# Only the password-LOGIN endpoint is throttled (brute-force target). Refresh
# and logout are excluded: the SPA calls /session/refresh automatically on every
# load and after any 401, so throttling it would 429 normal use (reloads, extra
# tabs) — which locked users out in prod.
_LOGIN_PATH = "/api/v1/auth/session"


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client sliding-window limit on the password-login endpoint.

    In-process (per replica) — a defence-in-depth floor against single-source
    brute force, not a substitute for a gateway/distributed limit at scale.
    """

    def __init__(self, app, *, max_requests: int = 10, window_seconds: float = 60.0):
        super().__init__(app)
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _limited_path(self, path: str) -> bool:
        # Exact login path only — NOT the /session/refresh or /session/logout
        # sub-paths.
        return path.rstrip("/") == _LOGIN_PATH

    def _client_key(self, request: Request) -> str:
        # Behind the proxy, request.client is the proxy; the real client is the
        # first hop of X-Forwarded-For. Keying on the proxy IP would make every
        # user share one bucket and 429 everyone at once.
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        if not self._limited_path(request.url.path):
            return await call_next(request)
        client = self._client_key(request)
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
