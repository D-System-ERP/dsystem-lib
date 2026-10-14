import os
from collections.abc import Collection
from uuid import UUID

from dsystem.cache import cache_aside, cache_invalidate
from dsystem.clients.service import ServiceClient
from dsystem.dependencies.auth import TokenPayload, _decode_permissions, _decode_stage_filters

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

    async def user_permissions(self, organization_id: UUID | str, user_ids: Collection[UUID]) -> list[dict]:
        body = {"organization_id": str(organization_id), "user_ids": [str(user_id) for user_id in user_ids]}
        return await self.post("/api/internal/users/permissions", body)


async def viewers(organization_id: UUID, user_ids: Collection[UUID]) -> dict[UUID, TokenPayload]:
    """Each active person of the organization as their access token would read — what a service checks before it tells
    someone of a record (`Requires(...)(viewer)` answers as for a request of theirs). A missing person is left out; an
    auth that cannot answer raises."""
    if not user_ids:
        return {}
    rows = await AuthServiceClient().user_permissions(organization_id, user_ids)
    return {
        UUID(row["id"]): TokenPayload(
            user_id=UUID(row["id"]),
            org_id=organization_id,
            role_id=UUID(row["role_id"]) if row.get("role_id") else None,
            is_superuser=bool(row.get("is_superuser")),
            team_id=UUID(row["team_id"]) if row.get("team_id") else None,
            permissions=_decode_permissions(row.get("p") or {}),
            stage_filters=_decode_stage_filters(row.get("ps") or {}),
        )
        for row in rows
        if row.get("is_active", True)
    }


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
