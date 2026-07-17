"""auth-integration spec: JWKS verification, expiry, tenant claims,
introspection, and client-credentials."""

from __future__ import annotations

import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from cyberarche.adapters.outbound.auth.cyberdyne import (
    ClientCredentialsTokenSource,
    CyberdyneAuthConfig,
    JwksTokenVerifier,
)
from cyberarche.domain.errors import NotAuthenticated

KID = "test-key-1"
# issuer is set explicitly here (the wiring derives it from base_url in prod);
# it matches the iss that sign() stamps.
CONFIG = CyberdyneAuthConfig(
    base_url="https://auth.test",
    client_id="cyberarche",
    client_secret="s3cret",
    issuer="cyberdyne-auth",
)


@pytest.fixture(scope="module")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def jwks_for(key) -> dict:
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    return {"keys": [{**public_jwk, "kid": KID, "alg": "RS256", "use": "sig"}]}


def sign(key, *, kid: str = KID, **claims) -> str:
    # Real CyberdyneAuth tokens carry iss + exp; include them by default so the
    # verifier's issuer/expiry requirements (F-003/F-008) are exercised.
    payload = {"sub": "user-1", "iss": "cyberdyne-auth", "exp": time.time() + 300}
    payload.update(claims)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return jwt.encode(payload, pem, algorithm="RS256", headers={"kid": kid})


def http_with(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def auth_backend(key, *, token_response: dict | None = None, introspect: dict | None = None):
    calls = {"token": 0, "jwks": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/.well-known/jwks.json":
            calls["jwks"] += 1
            return httpx.Response(200, json=jwks_for(key))
        if request.url.path == "/api/v1/auth/oauth2/token":
            calls["token"] += 1
            return httpx.Response(200, json=token_response or {})
        if request.url.path == "/api/v1/auth/introspect":
            return httpx.Response(200, json=introspect or {"active": False})
        return httpx.Response(404)

    return handler, calls


async def test_valid_jwt_yields_claims_with_tenant_from_org_claim(rsa_key):
    handler, _ = auth_backend(rsa_key)
    verifier = JwksTokenVerifier(CONFIG, http_with(handler))

    claims = await verifier.verify(sign(rsa_key, org_id="acme", email="u@acme.test"))

    assert claims.subject == "user-1"
    assert claims.tenant_id == "acme"
    assert claims.email == "u@acme.test"


async def test_missing_org_claim_falls_back_to_personal_tenant(rsa_key):
    handler, _ = auth_backend(rsa_key)
    verifier = JwksTokenVerifier(CONFIG, http_with(handler))

    claims = await verifier.verify(sign(rsa_key))

    assert claims.tenant_id == claims.subject  # personal tenant


async def test_expired_jwt_is_rejected(rsa_key):
    handler, _ = auth_backend(rsa_key)
    verifier = JwksTokenVerifier(CONFIG, http_with(handler))

    with pytest.raises(NotAuthenticated):
        await verifier.verify(sign(rsa_key, exp=time.time() - 60))


async def test_bad_signature_is_rejected(rsa_key):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    handler, _ = auth_backend(rsa_key)  # JWKS serves rsa_key, token signed by other
    verifier = JwksTokenVerifier(CONFIG, http_with(handler))

    with pytest.raises(NotAuthenticated):
        await verifier.verify(sign(other_key))


async def test_opaque_token_uses_introspection(rsa_key):
    handler, _ = auth_backend(
        rsa_key,
        token_response={"access_token": "svc-token", "expires_in": 300},
        introspect={"active": True, "sub": "svc-user", "scope": "docs.read"},
    )
    http = http_with(handler)
    credentials = ClientCredentialsTokenSource(CONFIG, http)
    verifier = JwksTokenVerifier(CONFIG, http, credentials)

    claims = await verifier.verify("opaque-token-no-dots")

    assert claims.subject == "svc-user"
    assert "docs.read" in claims.scopes


async def test_client_credentials_token_is_cached(rsa_key):
    handler, calls = auth_backend(
        rsa_key, token_response={"access_token": "svc-token", "expires_in": 3600}
    )
    credentials = ClientCredentialsTokenSource(CONFIG, http_with(handler))

    first = await credentials.service_token()
    second = await credentials.service_token()

    assert first == second == "svc-token"
    assert calls["token"] == 1  # cached until near expiry


async def test_alg_none_token_is_rejected(rsa_key):
    """An unsigned `alg=none` token must never verify. Guards the verifier's
    cryptographic check (RS256 signature against the asymmetric JWKS): if
    signature verification were ever disabled, this would start passing."""
    handler, _ = auth_backend(rsa_key)
    verifier = JwksTokenVerifier(CONFIG, http_with(handler))

    unsigned = jwt.encode(
        {"sub": "attacker", "exp": time.time() + 300},
        key="",
        algorithm="none",
        headers={"kid": KID},
    )
    with pytest.raises(NotAuthenticated):
        await verifier.verify(unsigned)


async def test_hs256_token_is_rejected(rsa_key):
    """RS/HS algorithm-confusion regression: a symmetric HS256 token must never
    verify against the asymmetric JWKS, whatever HMAC secret the attacker chose
    (the verifier only validates RS256 signatures against the RSA key)."""
    handler, _ = auth_backend(rsa_key)
    verifier = JwksTokenVerifier(CONFIG, http_with(handler))

    forged = jwt.encode(
        {"sub": "attacker", "exp": time.time() + 300},
        key="attacker-chosen-secret",
        algorithm="HS256",
        headers={"kid": KID},
    )
    with pytest.raises(NotAuthenticated):
        await verifier.verify(forged)


def _sign_raw(key, payload: dict) -> str:
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return jwt.encode(payload, pem, algorithm="RS256", headers={"kid": KID})


async def test_wrong_issuer_is_rejected(rsa_key):
    """F-008: a validly-signed token from a different issuer must not verify."""
    handler, _ = auth_backend(rsa_key)
    verifier = JwksTokenVerifier(CONFIG, http_with(handler))

    with pytest.raises(NotAuthenticated):
        await verifier.verify(sign(rsa_key, iss="evil-issuer"))


async def test_missing_issuer_is_rejected(rsa_key):
    """F-008: issuer is required (not just validated-if-present)."""
    handler, _ = auth_backend(rsa_key)
    verifier = JwksTokenVerifier(CONFIG, http_with(handler))

    token = _sign_raw(rsa_key, {"sub": "user-1", "exp": time.time() + 300})
    with pytest.raises(NotAuthenticated):
        await verifier.verify(token)


async def test_missing_exp_is_rejected(rsa_key):
    """F-008: a token without an expiry must not be accepted as never-expiring."""
    handler, _ = auth_backend(rsa_key)
    verifier = JwksTokenVerifier(CONFIG, http_with(handler))

    token = _sign_raw(rsa_key, {"sub": "user-1", "iss": "cyberdyne-auth"})
    with pytest.raises(NotAuthenticated):
        await verifier.verify(token)


async def test_issuer_check_can_be_disabled(rsa_key):
    """With issuer=None an unsigned-issuer token verifies (opt-out escape hatch)."""
    handler, _ = auth_backend(rsa_key)
    verifier = JwksTokenVerifier(
        CyberdyneAuthConfig(base_url="https://auth.test", issuer=None),
        http_with(handler),
    )
    token = _sign_raw(rsa_key, {"sub": "u", "exp": time.time() + 300})
    claims = await verifier.verify(token)
    assert claims.subject == "u"


async def test_unknown_kid_does_not_hammer_jwks(rsa_key):
    """F-013: a burst of tokens with random unknown kids must not trigger a JWKS
    refetch per request."""
    handler, calls = auth_backend(rsa_key)
    verifier = JwksTokenVerifier(CONFIG, http_with(handler))

    for i in range(5):
        with pytest.raises(NotAuthenticated):
            await verifier.verify(sign(rsa_key, kid=f"random-{i}"))
    # One initial populate; the throttle floor prevents a fetch per unknown kid.
    assert calls["jwks"] <= 1


async def test_jwks_fetch_error_maps_to_not_authenticated(rsa_key):
    """F-013: a JWKS outage surfaces as 401, not an unhandled 500."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    verifier = JwksTokenVerifier(CONFIG, http_with(handler))
    with pytest.raises(NotAuthenticated):
        await verifier.verify(sign(rsa_key))
