import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dsystem.events.consumer import start_consumer
from dsystem.events.envelope import unwrap
from dsystem.events.inbox import event_time, run_once
from dsystem.models.user_replica import UserReplica
from dsystem.utils.timezone import utc_now

logger = logging.getLogger(__name__)

USER_FIELDS = (
    "username",
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


async def _locked(session: AsyncSession, user_id: UUID) -> UserReplica | None:
    stmt = select(UserReplica).where(UserReplica.id == user_id).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


def _stale(replica: UserReplica) -> bool:
    version = event_time()
    return version is not None and replica.source_updated_at is not None and version < replica.source_updated_at


async def _handle_user_created(session: AsyncSession, data: dict):
    if not data.get("organization_id"):
        return
    user_id = UUID(str(data["id"]))
    replica = await _locked(session, user_id)
    if replica is None:
        session.add(
            UserReplica(
                id=user_id,
                organization_id=UUID(str(data["organization_id"])),
                source_updated_at=event_time(),
                **replica_values(data),
            )
        )
        return
    if _stale(replica):
        return
    for field, value in replica_values(data).items():
        setattr(replica, field, value)
    replica.deleted_at = None
    replica.source_updated_at = event_time() or replica.source_updated_at


async def _handle_user_updated(session: AsyncSession, data: dict):
    await _handle_user_created(session, data)


async def _handle_user_deleted(session: AsyncSession, data: dict):
    replica = await _locked(session, UUID(str(data["id"])))
    if replica is None or _stale(replica):
        return
    replica.deleted_at = utc_now()
    replica.is_active = False
    replica.source_updated_at = event_time() or replica.source_updated_at


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
    await run_once(session_factory, namespace, meta.event_id, handler, data, occurred_at=meta.occurred_at)


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
