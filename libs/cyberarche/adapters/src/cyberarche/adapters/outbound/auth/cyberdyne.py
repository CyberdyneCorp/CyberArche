"""CyberdyneAuth adapters (auth-integration spec).

- JwksTokenVerifier: verifies RS256 JWTs against the auth service's JWKS,
  with introspection fallback for opaque/service tokens.
- ClientCredentialsTokenSource: OAuth2 client-credentials for
  service-to-service calls (workers, RAG).
- IamAuthorization: delegates permission evaluation to CyberdyneAuth IAM.

Tenant claim: CyberArche reads the tenant from a configurable claim
(default "org_id"); when absent, the user is their own tenant (personal
tenant = subject). This keeps single-user accounts working without an
organization while staying non-spoofable — the value always comes from
the verified token.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
import jwt
from jwt import InvalidTokenError, PyJWK

from cyberarche.application.ports.identity import (
    Claims,
    DirectoryPage,
    DirectoryUser,
    TokenPair,
)
from cyberarche.domain.errors import NotAuthenticated, UpstreamUnavailable

_JWKS_TTL_SECONDS = 300.0
# Floor between JWKS refetches triggered by an unknown `kid`, so a stream of
# tokens carrying random (attacker-chosen, unsigned) kids can't amplify into
# unbounded outbound requests to the IdP (security audit F-013).
_JWKS_MIN_REFRESH_INTERVAL_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class CyberdyneAuthConfig:
    base_url: str
    client_id: str = ""
    client_secret: str = ""
    audience: str | None = None
    # Expected `iss` claim. Enforced when set; the wiring defaults it to the auth
    # service's own base URL — the OIDC issuer — so a token from a different
    # issuer is rejected even if its signature validates against a JWKS key
    # (security audit F-008). Deriving it from base_url (rather than hard-coding
    # a name) keeps it aligned when the auth service changes its issuer string.
    issuer: str | None = None
    tenant_claim: str = "org_id"

    @property
    def jwks_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/.well-known/jwks.json"

    @property
    def token_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/v1/auth/oauth2/token"

    @property
    def introspect_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/v1/auth/introspect"

    @property
    def iam_evaluate_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/v1/admin/iam/evaluate"

    def org_members_url(self, org_id: str) -> str:
        return f"{self.base_url.rstrip('/')}/api/v1/orgs/{org_id}/members"

    @property
    def login_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/v1/auth/login"

    @property
    def refresh_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/v1/auth/refresh"


def _tenant_from_payload(payload: dict, tenant_claim: str) -> str:
    """The org id from the configured claim, tolerating CyberdyneAuth's shapes.

    CyberdyneAuth emits the organization as a nested object claim
    (`org: {id, short_name}`), not a flat `org_id` string, so a flat lookup
    alone would silently classify every org user as a personal tenant.
    Resolution order: flat claim, dotted path (`org.id`), then the `org`
    object's `id`. A dict value contributes its `id` field.
    """
    value = payload.get(tenant_claim)
    if value is None and "." in tenant_claim:
        value = payload
        for part in tenant_claim.split("."):
            value = value.get(part) if isinstance(value, dict) else None
    if value is None:
        org = payload.get("org")
        value = org.get("id") if isinstance(org, dict) else None
    if isinstance(value, dict):
        value = value.get("id")
    return str(value or "")


def claims_from_payload(payload: dict, *, tenant_claim: str) -> Claims:
    subject = str(payload.get("sub") or "")
    if not subject:
        raise NotAuthenticated("token has no subject")
    scopes = frozenset(str(payload.get("scope", "")).split()) - {""}
    tenant = _tenant_from_payload(payload, tenant_claim) or subject  # personal fallback
    return Claims(
        subject=subject,
        tenant_id=tenant,
        email=payload.get("email"),
        scopes=scopes,
        is_service=payload.get("token_use") == "client" or "client_id" in payload,
    )


class JwksTokenVerifier:
    """TokenPort adapter: JWT via JWKS, introspection for non-JWT tokens."""

    def __init__(
        self,
        config: CyberdyneAuthConfig,
        http: httpx.AsyncClient,
        service_tokens: "ClientCredentialsTokenSource | None" = None,
    ) -> None:
        self._config = config
        self._http = http
        self._service_tokens = service_tokens
        self._jwks: dict[str, PyJWK] = {}
        self._jwks_fetched_at = 0.0

    async def verify(self, token: str) -> Claims:
        if token.count(".") == 2:
            return await self._verify_jwt(token)
        return await self._introspect(token)

    async def _verify_jwt(self, token: str) -> Claims:
        try:
            kid = jwt.get_unverified_header(token).get("kid")
        except InvalidTokenError as error:
            raise NotAuthenticated(f"malformed token: {error}") from error
        key = await self._key_for(kid)
        if key is None:
            raise NotAuthenticated("no matching signing key")
        required = ["exp", "sub"]
        if self._config.issuer is not None:
            required.append("iss")
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self._config.audience,
                issuer=self._config.issuer,
                options={
                    # `exp` and `iss` (when configured) must be present, not just
                    # valid-if-present (audit F-008); aud is verified only when an
                    # audience is configured (audit F-003 — tokens are aud-less
                    # until CyberdyneAuth stamps a per-client audience).
                    "require": required,
                    "verify_aud": self._config.audience is not None,
                    "verify_iss": self._config.issuer is not None,
                },
            )
        except InvalidTokenError as error:
            raise NotAuthenticated(f"invalid token: {error}") from error
        return claims_from_payload(payload, tenant_claim=self._config.tenant_claim)

    async def _key_for(self, kid: str | None) -> PyJWK | None:
        age = time.monotonic() - self._jwks_fetched_at
        stale = age > _JWKS_TTL_SECONDS
        # An unknown kid triggers a refresh, but not more often than the floor —
        # otherwise unsigned attacker-chosen kids amplify into IdP traffic (F-013).
        unknown_kid = kid is not None and kid not in self._jwks
        if stale or (unknown_kid and age > _JWKS_MIN_REFRESH_INTERVAL_SECONDS):
            await self._refresh_jwks()
        if kid is not None:
            return self._jwks.get(kid)
        return next(iter(self._jwks.values()), None)

    async def _refresh_jwks(self) -> None:
        try:
            response = await self._http.get(self._config.jwks_url)
            response.raise_for_status()
        except httpx.HTTPError as error:
            # A JWKS outage is an auth failure, not a 500 (audit F-013).
            raise NotAuthenticated("cannot reach the signing-key endpoint") from error
        keys = response.json().get("keys", [])
        self._jwks = {k["kid"]: PyJWK.from_dict(k) for k in keys if "kid" in k}
        self._jwks_fetched_at = time.monotonic()

    async def _introspect(self, token: str) -> Claims:
        """RFC 7662 introspection — requires a service token."""
        if self._service_tokens is None:
            raise NotAuthenticated("opaque tokens not supported without introspection")
        service_token = await self._service_tokens.service_token()
        response = await self._http.post(
            self._config.introspect_url,
            data={"token": token},
            headers={"Authorization": f"Bearer {service_token}"},
        )
        if response.status_code != 200:
            raise NotAuthenticated("introspection failed")
        payload = response.json()
        if not payload.get("active"):
            raise NotAuthenticated("token is not active")
        return claims_from_payload(payload, tenant_claim=self._config.tenant_claim)


class ClientCredentialsTokenSource:
    """ServiceTokenPort adapter: RFC 6749 client-credentials with caching."""

    def __init__(self, config: CyberdyneAuthConfig, http: httpx.AsyncClient) -> None:
        self._config = config
        self._http = http
        self._token: str | None = None
        self._expires_at = 0.0

    async def service_token(self) -> str:
        if self._token is None or time.monotonic() >= self._expires_at - 30.0:
            await self._fetch()
        assert self._token is not None
        return self._token

    async def _fetch(self) -> None:
        response = await self._http.post(
            self._config.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._config.client_id,
                "client_secret": self._config.client_secret,
            },
        )
        if response.status_code != 200:
            raise NotAuthenticated("client-credentials grant failed")
        payload = response.json()
        self._token = payload["access_token"]
        self._expires_at = time.monotonic() + float(payload.get("expires_in", 300))


class CyberdyneAuthGateway:
    """AuthGatewayPort adapter: forwards SPA credential exchanges."""

    def __init__(self, config: CyberdyneAuthConfig, http: httpx.AsyncClient) -> None:
        self._config = config
        self._http = http

    async def password_login(self, *, email: str, password: str) -> TokenPair:
        response = await self._http.post(
            self._config.login_url, json={"email": email, "password": password}
        )
        if response.status_code != 200:
            raise NotAuthenticated("invalid credentials")
        return _token_pair(response.json())

    async def refresh(self, *, refresh_token: str) -> TokenPair:
        response = await self._http.post(
            self._config.refresh_url, json={"refresh_token": refresh_token}
        )
        if response.status_code != 200:
            raise NotAuthenticated("refresh token rejected")
        return _token_pair(response.json())


def _token_pair(payload: dict) -> TokenPair:
    access, refresh = payload.get("access_token"), payload.get("refresh_token")
    if not access or not refresh:
        raise NotAuthenticated("auth service returned no tokens")
    return TokenPair(access_token=access, refresh_token=refresh)


class CyberdyneDirectory:
    """DirectoryPort adapter: lists an organization's users for pickers.

    Authenticates with our own service token (client-credentials holding the
    `directory:read` grant) — never the caller's token. Any failure maps to
    UpstreamUnavailable so the SPA can fall back to raw-id entry
    (org-directory spec)."""

    def __init__(
        self,
        config: CyberdyneAuthConfig,
        http: httpx.AsyncClient,
        service_tokens: ClientCredentialsTokenSource,
    ) -> None:
        self._config = config
        self._http = http
        self._service_tokens = service_tokens

    async def list_org_users(
        self,
        org_id: str,
        *,
        search: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> DirectoryPage:
        params: dict[str, str | int] = {"page": page, "page_size": page_size}
        if search:
            params["search"] = search
        try:
            token = await self._service_tokens.service_token()
            response = await self._http.get(
                self._config.org_members_url(org_id),
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        except (httpx.HTTPError, NotAuthenticated) as error:
            raise UpstreamUnavailable("user directory unreachable") from error
        if response.status_code == 404:
            # Unknown/inactive org: an empty directory, not an outage.
            return DirectoryPage(users=[], total=0, page=page, page_size=page_size)
        if response.status_code != 200:
            raise UpstreamUnavailable(
                f"user directory returned {response.status_code}"
            )
        return _directory_page(response.json(), page=page, page_size=page_size)


def _directory_page(payload: dict, *, page: int, page_size: int) -> DirectoryPage:
    users = [
        DirectoryUser(
            id=str(member.get("id") or ""),
            email=member.get("email"),
            avatar_url=member.get("avatar_url"),
            is_active=bool(member.get("is_active", True)),
        )
        for member in payload.get("members", [])
        if member.get("id")
    ]
    return DirectoryPage(
        users=users,
        total=int(payload.get("total", len(users))),
        page=int(payload.get("page", page)),
        page_size=int(payload.get("page_size", page_size)),
    )


class IamAuthorization:
    """AuthorizationPort adapter delegating to CyberdyneAuth IAM evaluate."""

    def __init__(
        self,
        config: CyberdyneAuthConfig,
        http: httpx.AsyncClient,
        service_tokens: ClientCredentialsTokenSource,
    ) -> None:
        self._config = config
        self._http = http
        self._service_tokens = service_tokens

    async def evaluate(self, *, user_id: str, action: str, resource: str) -> bool:
        service_token = await self._service_tokens.service_token()
        response = await self._http.post(
            self._config.iam_evaluate_url,
            json={"user_id": user_id, "action": action, "resource": resource},
            headers={"Authorization": f"Bearer {service_token}"},
        )
        if response.status_code != 200:
            return False
        return bool(response.json().get("allowed", False))
