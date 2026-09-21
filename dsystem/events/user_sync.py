import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dsystem.cache import run_claimed
from dsystem.events.consumer import start_consumer
from dsystem.events.envelope import unwrap
from dsystem.models.user_replica import UserReplica

logger = logging.getLogger(__name__)

USER_FIELDS = (
    "email",
    "first_name",
    "last_name",
    "middle_name",
    "phone",
    "picture_url",
    "role_id",
    "team_id",
    "default_legal_entity_id",
    "is_active",
)
_UUID_FIELDS = frozenset({"role_id", "team_id", "default_legal_entity_id"})


def _coerce(field: str, value):
    if field in _UUID_FIELDS and value is not None and not isinstance(value, UUID):
        return UUID(str(value))
    return value


def replica_values(data: dict) -> dict:
    return {k: _coerce(k, data.get(k)) for k in USER_FIELDS if k in data}


async def _handle_user_created(session: AsyncSession, data: dict):
    if not data.get("organization_id"):
        return
    existing = await session.execute(select(UserReplica).where(UserReplica.id == UUID(data["id"])))
    replica = existing.scalar_one_or_none()
    if replica:
        for field, value in replica_values(data).items():
            setattr(replica, field, value)
        return
    session.add(UserReplica(id=UUID(data["id"]), organization_id=UUID(data["organization_id"]), **replica_values(data)))


async def _handle_user_updated(session: AsyncSession, data: dict):
    result = await session.execute(select(UserReplica).where(UserReplica.id == UUID(data["id"])))
    replica = result.scalar_one_or_none()
    if not replica:
        return await _handle_user_created(session, data)
    for field, value in replica_values(data).items():
        setattr(replica, field, value)


async def _handle_user_deleted(session: AsyncSession, data: dict):
    result = await session.execute(select(UserReplica).where(UserReplica.id == UUID(data["id"])))
    replica = result.scalar_one_or_none()
    if replica:
        await session.delete(replica)


HANDLERS = {
    "user.created": _handle_user_created,
    "user.updated": _handle_user_updated,
    "user.deleted": _handle_user_deleted,
}


async def _dispatch(session_factory: async_sessionmaker, routing_key: str, body: dict, namespace: str):
    handler = HANDLERS.get(routing_key)
    if not handler:
        return
    data, meta = unwrap(body, routing_key)

    async def run():
        async with session_factory() as session:
            await handler(session, data)
            await session.commit()

    await run_claimed(meta.event_id, namespace, run)


async def start_user_sync_consumer(rabbitmq_url: str, session_factory: async_sessionmaker, service_name: str):
    queue_name = f"{service_name}-user-sync"

    async def dispatch(routing_key: str, body: dict):
        await _dispatch(session_factory, routing_key, body, queue_name)

    return await start_consumer(
        rabbitmq_url=rabbitmq_url,
        queue_name=queue_name,
        routing_keys=list(HANDLERS.keys()),
        handler=dispatch,
    )


async def bootstrap_users(session_factory: async_sessionmaker, auth_service_url: str, service_secret: str):
    import httpx
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    async with session_factory() as session:
        seeded = (await session.execute(select(UserReplica.id).limit(1))).first() is not None
    if seeded:
        return

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{auth_service_url}/api/internal/users",
                headers={"X-Service-Secret": service_secret},
            )
            resp.raise_for_status()
            users = resp.json()
    except Exception:
        logger.warning("Failed to bootstrap users from auth service", exc_info=True)
        return

    records = [
        {"id": UUID(u["id"]), "organization_id": UUID(u["organization_id"]), **replica_values(u)}
        for u in users
        if u.get("organization_id")
    ]
    if not records:
        return

    async with session_factory() as session:
        stmt = pg_insert(UserReplica).values(records).on_conflict_do_nothing(index_elements=["id"])
        await session.execute(stmt)
        await session.commit()
    logger.info("Bootstrapped %d user replicas", len(records))
