"""Personal API keys (auth-integration spec): mint credentials for
external MCP clients. The secret appears exactly once, in the create
response."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.domain.api_keys import ApiKey

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    created_at: datetime
    expires_at: datetime | None
    revoked: bool
    last_used_at: datetime | None

    @staticmethod
    def from_domain(key: ApiKey) -> "ApiKeyResponse":
        return ApiKeyResponse(
            id=key.id,
            name=key.name,
            prefix=key.prefix,
            created_at=key.created_at,
            expires_at=key.expires_at,
            revoked=key.revoked_at is not None,
            last_used_at=key.last_used_at,
        )


class CreatedApiKeyResponse(ApiKeyResponse):
    secret: str  # shown exactly once


@router.post("", status_code=201)
async def create_api_key(
    body: CreateApiKeyRequest, cases: Cases, caller: Caller
) -> CreatedApiKeyResponse:
    created = await cases.api_keys.create(
        caller, name=body.name, expires_at=body.expires_at
    )
    base = ApiKeyResponse.from_domain(created.key)
    return CreatedApiKeyResponse(**base.model_dump(), secret=created.secret)


@router.get("")
async def list_api_keys(cases: Cases, caller: Caller) -> list[ApiKeyResponse]:
    keys = await cases.api_keys.list(caller)
    return [ApiKeyResponse.from_domain(k) for k in keys]


@router.delete("/{key_id}")
async def revoke_api_key(key_id: str, cases: Cases, caller: Caller) -> ApiKeyResponse:
    revoked = await cases.api_keys.revoke(caller, key_id)
    return ApiKeyResponse.from_domain(revoked)
