"""Notification preferences endpoints (notifications spec): the caller reads and
updates their own delivery preferences. In-app is always on and not exposed."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from cyberarche.adapters.inbound.http.dependencies import Caller, Cases
from cyberarche.domain.notifications import NotificationPreferences

router = APIRouter(tags=["notifications"])


class NotificationPreferencesResponse(BaseModel):
    email_enabled: bool
    push_enabled: bool
    mentions_enabled: bool
    agent_results_enabled: bool

    @staticmethod
    def from_domain(
        prefs: NotificationPreferences,
    ) -> "NotificationPreferencesResponse":
        return NotificationPreferencesResponse(
            email_enabled=prefs.email_enabled,
            push_enabled=prefs.push_enabled,
            mentions_enabled=prefs.mentions_enabled,
            agent_results_enabled=prefs.agent_results_enabled,
        )


class NotificationPreferencesRequest(BaseModel):
    email_enabled: bool
    push_enabled: bool
    mentions_enabled: bool
    agent_results_enabled: bool


@router.get("/api/v1/notification-preferences")
async def get_preferences(
    cases: Cases, caller: Caller
) -> NotificationPreferencesResponse:
    prefs = await cases.notification_prefs.get(caller)
    return NotificationPreferencesResponse.from_domain(prefs)


@router.put("/api/v1/notification-preferences")
async def update_preferences(
    body: NotificationPreferencesRequest, cases: Cases, caller: Caller
) -> NotificationPreferencesResponse:
    prefs = await cases.notification_prefs.update(
        caller,
        email_enabled=body.email_enabled,
        push_enabled=body.push_enabled,
        mentions_enabled=body.mentions_enabled,
        agent_results_enabled=body.agent_results_enabled,
    )
    return NotificationPreferencesResponse.from_domain(prefs)
