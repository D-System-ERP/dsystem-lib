import os
from uuid import UUID

from dsystem.cache import cache_aside, cache_invalidate
from dsystem.clients.service import ServiceClient

_TTL_SECONDS = 300


def _base_url() -> str:
    return os.environ.get("AUTH_URL") or os.environ.get("AUTH_SERVICE_URL", "http://localhost:8000")


class AuthServiceClient(ServiceClient):
    def __init__(self, base_url: str | None = None, *, service_secret: str | None = None):
        super().__init__(base_url or _base_url(), service_secret=service_secret)

    async def organization(self, organization_id: UUID | str) -> dict:
        return await self.get(f"/api/internal/organizations/{organization_id}")

    async def organizations(self) -> list[dict]:
        return await self.get("/api/internal/organizations")

    async def users(self, organization_id: UUID | str | None = None) -> list[dict]:
        params = {"organization_id": str(organization_id)} if organization_id else None
        return await self.get("/api/internal/users", params=params)

    async def legal_entities(self, organization_id: UUID | str | None = None) -> list[dict]:
        params = {"organization_id": str(organization_id)} if organization_id else None
        return await self.get("/api/internal/legal-entities", params=params)


async def organization_settings(organization_id: UUID | str) -> dict:
    """The organization row (timezone, base currency, costing/lot policy), cached for 5 minutes.

    For contexts with no request token — Celery tasks and event consumers. A lookup
    failure surfaces to the caller: an organization always exists.
    """

    async def _load() -> dict:
        return await AuthServiceClient().organization(organization_id)

    return await cache_aside(organization_settings_key(organization_id), _load, ttl=_TTL_SECONDS)


def organization_settings_key(organization_id: UUID | str) -> str:
    return f"org:settings:{organization_id}"


async def forget_organization_settings(organization_id: UUID | str) -> None:
    """Drop the shared settings cache so every service reads the new policy on its next lookup."""
    await cache_invalidate(organization_settings_key(organization_id))


async def org_timezone(organization_id: UUID | str) -> str:
    data = await organization_settings(organization_id)
    tz = data.get("timezone")
    if not tz:
        raise LookupError(f"organization {organization_id} has no timezone")
    return tz
