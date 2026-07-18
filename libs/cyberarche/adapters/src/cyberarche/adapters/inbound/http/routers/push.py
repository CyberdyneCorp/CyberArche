"""Web Push endpoints (notifications spec): expose the VAPID public key the
browser needs to subscribe, and register/remove the caller's own browser push
subscriptions. The public key is empty when push is unconfigured, which the
frontend treats as "push not available"."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import (
    Caller,
    Cases,
    get_container,
)

router = APIRouter(tags=["notifications"])


class VapidKeyResponse(BaseModel):
    key: str


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class SubscribeRequest(BaseModel):
    """The standard browser PushSubscription JSON shape (subscription.toJSON())."""

    endpoint: str
    keys: PushKeys


class UnsubscribeRequest(BaseModel):
    endpoint: str


@router.get("/api/v1/push/vapid-public-key")
def vapid_public_key(container=Depends(get_container)) -> VapidKeyResponse:
    return VapidKeyResponse(key=container.config.push_vapid_public_key)


@router.post("/api/v1/push/subscriptions", status_code=204)
async def subscribe(body: SubscribeRequest, cases: Cases, caller: Caller) -> None:
    await cases.push_subscriptions.subscribe(
        caller,
        endpoint=body.endpoint,
        p256dh=body.keys.p256dh,
        auth=body.keys.auth,
    )


@router.delete("/api/v1/push/subscriptions", status_code=204)
async def unsubscribe(
    body: UnsubscribeRequest, cases: Cases, caller: Caller
) -> None:
    await cases.push_subscriptions.unsubscribe(caller, endpoint=body.endpoint)
